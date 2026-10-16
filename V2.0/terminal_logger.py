#!/usr/bin/env python3
"""Run an interactive Bash through util-linux script and log visible output.

The terminal receives the complete stream. The log omits content emitted while
an ANSI alternate screen (commonly used by mc/btop) is active.
"""

import codecs
import datetime
import os
import pwd
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time



LOG_DIR = os.path.expanduser("~/terminallogs")
LOG_TERMINAL_HISTORY = True
LOG_TERMINAL_HISTORY_TIME_STAMPED = False
LOG_LIVE_BASH_HISTORY = False
LOG_LIVE_BASH_HISTORY_TIME_STAMPED = False


def open_logs():
    modes = {"TH": LOG_TERMINAL_HISTORY,
             "TH-TS": LOG_TERMINAL_HISTORY_TIME_STAMPED,
             "LBH": LOG_LIVE_BASH_HISTORY,
             "LBH-TS": LOG_LIVE_BASH_HISTORY_TIME_STAMPED}
    enabled = [name for name, value in modes.items() if value]
    if not enabled:
        return {}
    os.makedirs(LOG_DIR, mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    hostname = socket.gethostname().split(".", 1)[0]
    username = pwd.getpwuid(os.getuid()).pw_name
    hostname = re.sub(r"[^\w.-]", "_", hostname, flags=re.UNICODE)
    username = re.sub(r"[^\w.-]", "_", username, flags=re.UNICODE)
    base = f"terminal_{hostname}_{username}_{stamp}"
    suffix = 0
    while True:
        files = {}
        paths = []
        try:
            for mode in enabled:
                name = base + (f"_{suffix}" if suffix else "") + f"-{mode}.log"
                path = os.path.join(LOG_DIR, name)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                paths.append(path)
                files[mode] = os.fdopen(fd, "wb", buffering=0)
            return files
        except FileExistsError:
            suffix += 1
        finally:
            if len(files) != len(enabled):
                for file in files.values():
                    file.close()
                for path in paths:
                    os.unlink(path)


def follow_commands(path, child, files):
    pending = bytearray()
    fields = []
    with open(path, "rb", buffering=0) as raw:
        while True:
            data = raw.read(4096)
            exited = not data and child.poll() is not None
            if exited:
                data = raw.read(4096)
            if data:
                pending.extend(data)
                while b"\0" in pending:
                    field, _, remainder = pending.partition(b"\0")
                    pending = bytearray(remainder)
                    fields.append(field)
                    if len(fields) == 2:
                        stamp, command = fields
                        if "LBH" in files:
                            files["LBH"].write(command + b"\n")
                        if "LBH-TS" in files:
                            files["LBH-TS"].write(stamp + b" " + command + b"\n")
                        fields.clear()
            elif exited:
                break
            else:
                time.sleep(0.02)


class TranscriptWriter:
    """Write/replace the current text line while keeping previous lines intact."""
    def __init__(self, files):
        self.plain = files.get("TH")
        self.stamped = files.get("TH-TS")
        self.starts = {file: file.tell() for file in (self.plain, self.stamped) if file is not None}
        self.stamp = None
        self.current = bytearray()

    def update_line(self, data, *, complete=False):
        if self.stamp is None and (data or complete):
            self.stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S ").encode()
        for file, start in self.starts.items():
            file.seek(start)
            prefix = (self.stamp or b"") if file is self.stamped else b""
            file.write(prefix + data + (b"\n" if complete else b""))
            file.truncate()
            if complete:
                self.starts[file] = file.tell()
        if complete:
            self.stamp = None

    def write(self, data):
        # Also support ordinary incremental text writers and direct tests.
        parts = data.split(b"\n")
        for index, part in enumerate(parts):
            self.current.extend(part)
            complete = index < len(parts) - 1
            if self.current or complete:
                self.update_line(bytes(self.current), complete=complete)
            if complete:
                self.current.clear()


class TranscriptLine:
    """Handle common single-line Readline redraws, not a full screen emulator."""
    def __init__(self, writer):
        self.writer = writer if hasattr(writer, "update_line") else TranscriptWriter({"TH": writer})
        self.decoder = codecs.getincrementaldecoder("utf-8")("surrogateescape")
        self.line = []
        self.cursor = 0
        self.dirty = False

    def save(self, complete=False):
        if self.dirty or complete:
            self.writer.update_line("".join(self.line).encode("utf-8", "surrogateescape"), complete=complete)
            self.dirty = False
        if complete:
            self.line.clear()
            self.cursor = 0

    def write(self, data):
        for char in self.decoder.decode(data):
            if char == "\r":
                self.cursor = 0
            elif char == "\b":
                self.cursor = max(0, self.cursor - 1)
            elif char == "\n":
                self.save(complete=True)
            else:
                if self.cursor > len(self.line):
                    self.line.extend(" " * (self.cursor - len(self.line)))
                if self.cursor < len(self.line):
                    self.line[self.cursor] = char
                else:
                    self.line.append(char)
                self.cursor += 1
                self.dirty = True
        self.save()

    def control(self, body, final):
        if not re.fullmatch(rb"[0-9;]*", body):
            return
        args = body.split(b";")
        value = int(args[0] or b"0")
        # Restrict hostile cursor arguments; normal terminal columns are small.
        value = min(value, 65536)
        if final in b"G`":
            self.cursor = max(0, value - 1)
        elif final == ord("C"):
            self.cursor = min(65536, self.cursor + (value or 1))
        elif final == ord("D"):
            self.cursor = max(0, self.cursor - (value or 1))
        elif final == ord("K"):
            if value == 0:
                del self.line[self.cursor:]
            elif value == 1:
                end = min(len(self.line), self.cursor + 1)
                self.line[:end] = [" "] * end
            elif value == 2:
                self.line.clear()
            self.dirty = True
        self.save()

    def finish(self):
        final = self.decoder.decode(b"", final=True)
        if final:
            self.line.extend(final)
            self.dirty = True
        self.save()


def filter_stream(stream, log, *, display):
    """Filter controls and apply common in-line redraws across read boundaries."""
    rendered = TranscriptLine(log)
    active = True
    state = "normal"
    seq = bytearray()
    ordinary = bytearray()

    def flush():
        if active and ordinary:
            rendered.write(bytes(ordinary))
        ordinary.clear()

    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        if display:
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
        for byte in chunk:
            if state == "normal":
                if byte == 0x1B:
                    flush()
                    state = "escape"
                elif byte in (0x08, 0x09, 0x0A, 0x0D) or byte >= 0x20 and byte != 0x7F:
                    ordinary.append(byte)
            elif state == "escape":
                if byte == ord("["):
                    seq.clear()
                    state = "csi"
                elif byte in b"]PX^_":
                    state = "osc" if byte == ord("]") else "string"
                elif 0x20 <= byte <= 0x2F:
                    state = "escape_intermediate"
                else:
                    state = "normal"
            elif state == "escape_intermediate":
                if not 0x20 <= byte <= 0x2F:
                    state = "normal"
            elif state == "csi":
                if 0x40 <= byte <= 0x7E:
                    if byte in b"hl" and seq.startswith(b"?"):
                        modes = set(bytes(seq[1:]).split(b";"))
                        if modes.intersection({b"47", b"1047", b"1049"}):
                            active = byte == ord("l")
                    elif active:
                        rendered.control(bytes(seq), byte)
                    seq.clear()
                    state = "normal"
                elif len(seq) < 128:
                    seq.append(byte)
                else:
                    seq.clear()
                    state = "discard_csi"
            elif state == "discard_csi":
                if 0x40 <= byte <= 0x7E:
                    state = "normal"
            elif state in ("osc", "string"):
                if byte == 0x1B:
                    string_state = state
                    state = "string_escape"
                elif state == "osc" and byte == 0x07:
                    state = "normal"
            elif state == "string_escape":
                if byte == ord("\\"):
                    state = "normal"
                elif byte != 0x1B:
                    state = string_state
        flush()
    rendered.finish()


def follow_output(path, timing_path, child, log):
    """Read exactly the output byte counts in script's advanced timing stream.

    The metadata header/footer never enter the filter, and no output suffix is
    withheld. Timing delays are not replayed: every available record is drained.
    """
    class LiveOutput:
        def __init__(self, raw, timing):
            self.raw = raw
            self.timing = timing
            self.remaining = 0
            self.header_read = False

        def read(self, size):
            if not self.header_read:
                header = bytearray()
                while not header.endswith(b"\n"):
                    data = self.raw.read(1)
                    if data:
                        header.extend(data)
                        if len(header) > 65536:
                            raise OSError("script metadata header exceeds 64 KiB")
                    elif child.poll() is not None:
                        data = self.raw.read(1)
                        if not data:
                            if header:
                                raise OSError("incomplete script metadata header")
                            return b""
                        header.extend(data)
                    else:
                        time.sleep(0.01)
                self.header_read = True
            while not self.remaining:
                record = bytearray()
                while not record.endswith(b"\n"):
                    data = self.timing.read(1)
                    if not data and child.poll() is not None:
                        data = self.timing.read(1)
                        if not data:
                            if record:
                                raise OSError("incomplete script timing record")
                            return b""
                    if data:
                        record.extend(data)
                        if len(record) > 65536:
                            raise OSError("script timing record exceeds 64 KiB")
                    else:
                        time.sleep(0.01)
                fields = record.split()
                if fields and fields[0] == b"O":
                    if len(fields) != 3 or not fields[2].isdigit():
                        raise OSError("invalid script output timing record")
                    self.remaining = int(fields[2])
            while True:
                data = self.raw.read(min(size, self.remaining))
                if not data and child.poll() is not None:
                    data = self.raw.read(min(size, self.remaining))
                    if not data:
                        raise OSError("script output shorter than its timing record")
                if data:
                    self.remaining -= len(data)
                    return data
                time.sleep(0.01)

    with open(path, "rb", buffering=0) as raw, open(timing_path, "rb", buffering=0) as timing:
        filter_stream(LiveOutput(raw, timing), log, display=False)


def main():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("terminal logger: run from an interactive terminal", file=sys.stderr)
        return 1
    try:
        logs = open_logs()
    except OSError as exc:
        print(f"terminal logger: cannot create log in {LOG_DIR}: {exc}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["TERMINAL_LOGGER_ACTIVE"] = "1"
    env.pop("TERMINAL_LOGGER_COMMAND_FILE", None)
    raw_path = None
    command_path = None
    timing_path = None
    errors = []

    def follow(target, *args):
        try:
            target(*args)
        except Exception as exc:
            errors.append(exc)
            print(f"terminal logger: logging failed: {exc}", file=sys.stderr)

    try:
        if not logs:
            # No pseudo-terminal or temporary log is needed in disabled mode.
            return subprocess.call(["bash", "-i"], env=env)
        if LOG_TERMINAL_HISTORY or LOG_TERMINAL_HISTORY_TIME_STAMPED:
            raw_fd, raw_path = tempfile.mkstemp(prefix="terminal-logger-", suffix=".raw")
            os.close(raw_fd)
            timing_fd, timing_path = tempfile.mkstemp(prefix="terminal-logger-", suffix=".timing")
            os.close(timing_fd)
        if LOG_LIVE_BASH_HISTORY or LOG_LIVE_BASH_HISTORY_TIME_STAMPED:
            command_fd, command_path = tempfile.mkstemp(prefix="terminal-logger-", suffix=".cmd")
            os.close(command_fd)
            env["TERMINAL_LOGGER_COMMAND_FILE"] = command_path
        script_args = ["script", "--quiet", "--flush", "--log-out", raw_path or os.devnull]
        if timing_path:
            script_args += ["--log-timing", timing_path, "--logging-format", "advanced"]
        child = subprocess.Popen(script_args + ["--command", "bash -i"], env=env)
        followers = []
        if raw_path:
            followers.append(threading.Thread(target=follow,
                args=(follow_output, raw_path, timing_path, child, TranscriptWriter(logs))))
        if command_path:
            followers.append(threading.Thread(target=follow,
                args=(follow_commands, command_path, child, logs)))
        for follower in followers:
            follower.start()
        status = child.wait()
        for follower in followers:
            follower.join()
        return 1 if errors else status
    except OSError as exc:
        print(f"terminal logger: cannot start recording (requires Bash and util-linux script): {exc}",
              file=sys.stderr)
        return 1
    finally:
        for log in logs.values():
            log.close()
        for path in (raw_path, timing_path, command_path):
            if path:
                try:
                    os.unlink(path)
                except OSError as exc:
                    print(f"terminal logger: cannot remove temporary file {path}: {exc}",
                          file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
