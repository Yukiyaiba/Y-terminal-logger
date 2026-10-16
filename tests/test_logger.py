"""Regression tests; all files and shell histories stay in temporary directories."""
import importlib.util
import io
import os
from pathlib import Path
import pty
import re
import select
import signal
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(version):
    spec = importlib.util.spec_from_file_location('logger_' + version.replace('.', '_'),
                                                  ROOT / version / 'terminal_logger.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULES = [load(version) for version in ('V1.0', 'V2.0')]


class Done:
    def poll(self):
        return 0


class Chunks:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def read(self, size):
        return next(self.chunks, b'')


class FilterTests(unittest.TestCase):
    def filtered(self, chunks):
        results = []
        for module in MODULES:
            out = io.BytesIO()
            module.filter_stream(Chunks(chunks), out, display=False)
            results.append(out.getvalue())
        self.assertEqual(results[0], results[1])
        return results[0]

    def test_split_sequences_and_utf8(self):
        data = 'árvíztűrő tükörfúrógép'.encode()
        self.assertEqual(self.filtered([b'\x1b[', b'31m' + data, b'\x1b[0m\r\n']), data + b'\n')

    def test_alternate_screen(self):
        for mode in (b'47', b'1047', b'1049'):
            self.assertEqual(self.filtered([b'yes\x1b[?' + mode + b'hsecret',
                                            b'\x1b[?' + mode + b'lend']), b'yesend')

    def test_control_strings(self):
        for introducer in (b']', b'P', b'X', b'^', b'_'):
            self.assertEqual(self.filtered([b'a\x1b' + introducer, b'private\x1b', b'\\b']), b'ab')
        self.assertEqual(self.filtered([b'a\x1b]title\x07b']), b'ab')

    def test_long_and_incomplete_controls(self):
        self.assertEqual(self.filtered([b'a\x1b]' + b'x' * 100000]), b'a')
        self.assertEqual(self.filtered([b'a\x1b[' + b'1' * 10000 + b'mb']), b'ab')

    def test_charset_and_c0_controls(self):
        self.assertEqual(self.filtered([b'a\x1b(Bb\x07\x00\x08\t\nc']), b'a\t\nc')

    def test_footer_text_does_not_truncate(self):
        body = b'first\nScript done on fake [COMMAND_EXIT_CODE="0"]\nSTILL HERE\n'
        for module in MODULES:
            with tempfile.TemporaryDirectory() as directory:
                raw = Path(directory) / 'raw'
                raw.write_bytes(b'Localized header\n' + body +
                                b'\nScript done on now [COMMAND_EXIT_CODE="0"]\n')
                out = io.BytesIO()
                timing = Path(directory) / "timing"
                timing.write_bytes(f"O 0 {len(body)}\n".encode())
                module.follow_output(raw, timing, Done(), out)
                self.assertEqual(out.getvalue(), body)

    def test_large_output_and_partial_final_line(self):
        body = b'x' * 20000 + b'\nlast'
        for module in MODULES:
            with tempfile.TemporaryDirectory() as directory:
                raw = Path(directory) / 'raw'
                raw.write_bytes(b'header\n' + body + b'\nLocalized footer [COMMAND_EXIT_CODE="7"]\n')
                out = io.BytesIO()
                timing = Path(directory) / "timing"
                timing.write_bytes(f"O 0 {len(body)}\n".encode())
                module.follow_output(raw, timing, Done(), out)
                self.assertEqual(out.getvalue(), body)

    def test_missing_footer_preserves_data(self):
        for module in MODULES:
            with tempfile.TemporaryDirectory() as directory:
                raw = Path(directory) / 'raw'
                body = b'body\n'
                raw.write_bytes(b'header\n' + body)
                out = io.BytesIO()
                timing = Path(directory) / "timing"
                timing.write_bytes(f"O 0 {len(body)}\n".encode())
                module.follow_output(raw, timing, Done(), out)
                self.assertEqual(out.getvalue(), b'body\n')

    def test_readline_redraw_is_not_concatenated(self):
        text = b'yuki@pluto:~$ bash -n ~/.bashrc'
        self.assertEqual(self.filtered([text, b'\r\x1b[K' + text + b'\r\n']), text + b'\n')

    def test_backspace_and_erase_line(self):
        self.assertEqual(self.filtered([b'abc\bZ\r\n']), b'abZ\n')
        self.assertEqual(self.filtered([b'long old command', b'\rnew\x1b[K\n']), b'new\n')

    def test_utf8_split_during_redraw(self):
        data = 'árvíz'.encode()
        self.assertEqual(self.filtered([data[:1], data[1:], b'\r', data[:3], data[3:], b'\n']), data + b'\n')

    def test_footer_shaped_output_at_end_is_preserved(self):
        body = b'\nScript done on fake [COMMAND_EXIT_CODE="0"]\n'
        for module in MODULES:
            with tempfile.TemporaryDirectory() as directory:
                raw = Path(directory) / 'raw'
                raw.write_bytes(b'header\n' + body + b'\nreal footer [COMMAND_EXIT_CODE="0"]\n')
                timing = Path(directory) / 'timing'
                timing.write_bytes(f'O 0 {len(body)}\nH 0 EXIT_CODE 0\n'.encode())
                out = io.BytesIO()
                module.follow_output(raw, timing, Done(), out)
                self.assertEqual(out.getvalue(), body)

    def test_inconsistent_timing_is_reported(self):
        for module in MODULES:
            with tempfile.TemporaryDirectory() as directory:
                raw = Path(directory) / 'raw'
                raw.write_bytes(b'header\nshort')
                timing = Path(directory) / 'timing'
                timing.write_bytes(b'O 0 50\n')
                with self.assertRaisesRegex(OSError, 'shorter'):
                    module.follow_output(raw, timing, Done(), io.BytesIO())

    def test_split_timing_records_and_final_drain(self):
        for module in MODULES:
            with tempfile.TemporaryDirectory() as directory:
                raw = Path(directory) / 'raw'
                raw.write_bytes(b'header\nfirstsecond\nfooter\n')
                timing = Path(directory) / 'timing'
                timing.write_bytes(b'H 0 START_TIME test\nO 0 5\nH 0 SIGNAL 28\nO 0 6\nH 0 EXIT_CODE 0\n')
                out = io.BytesIO()
                module.follow_output(raw, timing, Done(), out)
                self.assertEqual(out.getvalue(), b'firstsecond')


class FileTests(unittest.TestCase):
    def test_collision_and_permissions(self):
        for module in MODULES:
            with tempfile.TemporaryDirectory() as directory, patch.object(module, 'LOG_DIR', str(Path(directory) / 'logs')):
                def create():
                    return module.open_logs() if hasattr(module, 'open_logs') else {'TH': module.open_log()}
                first = create()
                second = create()
                for handle in [*first.values(), *second.values()]:
                    self.assertEqual(stat.S_IMODE(os.fstat(handle.fileno()).st_mode), 0o600)
                    handle.close()
                self.assertEqual(len(list(Path(module.LOG_DIR).glob('*.log'))), 2)
                self.assertEqual(stat.S_IMODE(Path(module.LOG_DIR).stat().st_mode), 0o700)

    def test_disabled_creates_nothing(self):
        module = MODULES[1]
        with tempfile.TemporaryDirectory() as directory:
            with patch.multiple(module, LOG_DIR=str(Path(directory) / 'logs'),
                                LOG_TERMINAL_HISTORY=False, LOG_TERMINAL_HISTORY_TIME_STAMPED=False,
                                LOG_LIVE_BASH_HISTORY=False, LOG_LIVE_BASH_HISTORY_TIME_STAMPED=False):
                self.assertEqual(module.open_logs(), {})
                self.assertFalse(Path(module.LOG_DIR).exists())

    def test_timestamped_lines(self):
        plain, stamped = io.BytesIO(), io.BytesIO()
        writer = MODULES[1].TranscriptWriter({'TH': plain, 'TH-TS': stamped})
        writer.write(b'one')
        writer.write(b' two\nthree\n')
        self.assertEqual(plain.getvalue(), b'one two\nthree\n')
        lines = stamped.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertRegex(lines[0], rb'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d one two$')
        self.assertTrue(lines[1].endswith(b' three'))

    def test_command_records_across_reads(self):
        plain, stamped = io.BytesIO(), io.BytesIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cmd'
            command = b'echo ' + b'x' * 9000 + b'\nsecond line'
            path.write_bytes(b'TIME\0' + command + b'\0NEXT\0exit\0unfinished')
            MODULES[1].follow_commands(path, Done(), {'LBH': plain, 'LBH-TS': stamped})
            self.assertEqual(plain.getvalue(), command + b'\nexit\n')
            self.assertEqual(stamped.getvalue(), b'TIME ' + command + b'\nNEXT exit\n')


def run_terminal(version, all_modes=True, history='ignoreboth', extra_rc='', commands=None, modes=None, on_prompt=None):
    """Exercise the complete script -> Bash -> PS0 -> follower pipeline on a PTY."""
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory)
        hook = ROOT / 'V2.0/terminal_logger_hook.bash'
        rc = ('PS1="LOGGER_READY> "; PS2="CONT> "; HISTSIZE=2; HISTCONTROL=' + history + '\n' +
              extra_rc + '\n' + (f'source "{hook}"\nsource "{hook}"\n' if version == 'V2.0' else ''))
        (home / '.bashrc').write_text(rc)
        (home / '.local/bin').mkdir(parents=True)
        (home / '.local/bin/terminal_logger_hook.bash').write_text(hook.read_text())
        module_path = ROOT / version / 'terminal_logger.py'
        code = (f'import importlib.util; s=importlib.util.spec_from_file_location("logger", {str(module_path)!r}); '
                'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                f'm.LOG_DIR={str(home / "terminallogs")!r}; ')
        if version == 'V2.0':
            code += f'm.LOG_TERMINAL_HISTORY=m.LOG_TERMINAL_HISTORY_TIME_STAMPED=m.LOG_LIVE_BASH_HISTORY=m.LOG_LIVE_BASH_HISTORY_TIME_STAMPED={all_modes!r}; '
        if modes is not None:
            for name, enabled in modes.items():
                code += f'm.{name}={enabled!r}; '
        code += 'raise SystemExit(m.main())'
        pid, fd = pty.fork()
        if pid == 0:
            os.environ.update(HOME=directory, SHELL='/bin/bash', TERM='xterm', TMPDIR=directory,
                              HISTFILE=str(home / 'history'))
            os.environ.pop('TERMINAL_LOGGER_ACTIVE', None)
            os.environ.pop('TERMINAL_LOGGER_COMMAND_FILE', None)
            os.execv(sys.executable, [sys.executable, '-c', code])
        output = bytearray()
        def wait_prompt():
            pending = bytearray()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if select.select([fd], [], [], .1)[0]:
                    try:
                        data = os.read(fd, 65536)
                    except OSError:
                        break
                    output.extend(data)
                    pending.extend(data)
                    if b'LOGGER_READY> ' in pending:
                        return
            raise AssertionError('Prompt timeout: ' + repr(bytes(output)))
        try:
            wait_prompt()
            if on_prompt:
                on_prompt(home, 0)
            for index, command in enumerate(commands or ['echo first', 'echo first', ' echo ignored', 'echo second',
                                        "printf '\\033[?1049hHIDDEN_ALT\\033[?1049lVISIBLE_END\\n'",
                                        "printf '\\nScript done on fake\\nAFTER_FAKE\\n'"]):
                os.write(fd, command.encode() + b'\n')
                wait_prompt()
                if on_prompt:
                    on_prompt(home, index + 1)
            os.write(fd, b'exit\n')
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                done, status = os.waitpid(pid, os.WNOHANG)
                if done:
                    if os.waitstatus_to_exitcode(status) != 0:
                        raise AssertionError('Logger failed: ' + repr(bytes(output)))
                    break
                if select.select([fd], [], [], .1)[0]:
                    try:
                        output.extend(os.read(fd, 65536))
                    except OSError:
                        pass
            else:
                raise AssertionError('Logger exit timeout')
        finally:
            os.close(fd)
            try:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            except ProcessLookupError:
                pass
            except ChildProcessError:
                pass
        logs = {p.name: p.read_bytes() for p in (home / 'terminallogs').glob('*.log')}
        raw_left = list(home.glob('terminal-logger-*'))
        return logs, output, raw_left


class IntegrationTests(unittest.TestCase):
    def test_all_modes_on_real_pty(self):
        logs, output, raw_left = run_terminal('V2.0')
        self.assertEqual(len(logs), 4)
        self.assertFalse(raw_left)
        transcript = next(v for k, v in logs.items() if k.endswith('-TH.log'))
        self.assertIn(b'VISIBLE_END', transcript)
        self.assertIn(b'AFTER_FAKE', transcript)
        self.assertNotIn(b'\x1b', transcript)
        self.assertNotIn(b'[COMMAND_EXIT_CODE=', transcript)
        stamped = next(v for k, v in logs.items() if k.endswith('-TH-TS.log'))
        self.assertEqual(re.sub(rb'(?m)^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', b'', stamped), transcript)
        # The echoed command contains HIDDEN_ALT, but its rendered output must not.
        self.assertNotIn(b'\nHIDDEN_ALT', transcript)
        commands = next(v for k, v in logs.items() if k.endswith('-LBH.log')).splitlines()
        self.assertEqual(commands.count(b'echo first'), 1)
        self.assertIn(b'echo second', commands)
        self.assertNotIn(b' echo ignored', commands)
        self.assertIn(b'exit', commands)

    def test_disabled_on_real_pty(self):
        logs, output, raw_left = run_terminal('V2.0', all_modes=False)
        self.assertEqual(logs, {})
        self.assertFalse(raw_left)
        self.assertIn(b'AFTER_FAKE', output)

    def test_v1_on_real_pty(self):
        logs, output, raw_left = run_terminal('V1.0')
        self.assertEqual(len(logs), 1)
        self.assertIn(b'AFTER_FAKE', next(iter(logs.values())))
        self.assertFalse(raw_left)

    def test_erasedups_and_status(self):
        logs, output, _ = run_terminal('V2.0', history='erasedups',
            extra_rc="PROMPT_COMMAND='printf \"STATUS=%s\\n\" \"$?\"'",
            commands=['echo first', 'echo second', 'echo first', 'false'])
        commands = next(v for k, v in logs.items() if k.endswith('-LBH.log')).splitlines()
        self.assertEqual(commands.count(b'echo first'), 2)
        self.assertIn(b'STATUS=1', output)

    def test_unset_histfile_does_not_clear_history(self):
        logs, _, _ = run_terminal('V2.0', extra_rc='unset HISTFILE',
                                  commands=['echo first', 'echo second'])
        commands = next(v for k, v in logs.items() if k.endswith('-LBH.log')).splitlines()
        self.assertEqual(commands, [b'echo first', b'echo second', b'exit'])

    def test_disabled_history_is_not_logged(self):
        logs, _, _ = run_terminal('V2.0', extra_rc='set +o history', commands=['echo first'])
        commands = next(v for k, v in logs.items() if k.endswith('-LBH.log'))
        self.assertEqual(commands, b'')

    def test_array_prompt_handler_status(self):
        logs, output, _ = run_terminal('V2.0',
            extra_rc="PROMPT_COMMAND=('printf \"ARRAY_STATUS=%s\\n\" \"$?\"')",
            commands=['false'])
        self.assertIn(b'ARRAY_STATUS=1', output)

    def test_command_only_mode(self):
        logs, output, raw_left = run_terminal('V2.0', all_modes=False,
            modes={'LOG_LIVE_BASH_HISTORY': True}, commands=['echo first'])
        self.assertEqual(len(logs), 1)
        self.assertTrue(next(iter(logs)).endswith('-LBH.log'))
        self.assertIn(b'echo first', next(iter(logs.values())))
        self.assertFalse(raw_left)


class LiveRegressionTests(unittest.TestCase):
    def test_user_commands_visible_before_exit(self):
        commands = ['bash -n ~/.bashrc', 'bash -n ~/.local/bin/terminal_logger_hook.bash',
                    'ls -lt ~/terminallogs | head']
        # A local log destination makes ls useful inside the isolated test home.
        for version in ('V1.0', 'V2.0'):
            with self.subTest(version=version):
                def inspect(home, count):
                    if not count:
                        return
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        paths = list((home / 'terminallogs').glob('*-TH.log' if version == 'V2.0' else '*.log'))
                        data = paths[0].read_bytes() if paths else b''
                        if all(command.encode() in data for command in commands[:count]):
                            if count < 3 or (b'total ' in data and b'.log' in data):
                                break
                        time.sleep(.02)
                    else:
                        self.fail(f'{version}: incomplete live transcript after command {count}: {data!r}')
                    if version == 'V2.0':
                        stamped = next((home / 'terminallogs').glob('*-TH-TS.log')).read_bytes()
                        self.assertIn(commands[count - 1].encode(), stamped)
                run_terminal(version, commands=commands, on_prompt=inspect)

    def test_partial_line_is_live_without_newline(self):
        for version in ('V1.0', 'V2.0'):
            with self.subTest(version=version):
                def inspect(home, count):
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        paths = list((home / 'terminallogs').glob('*-TH.log' if version == 'V2.0' else '*.log'))
                        text = paths[0].read_bytes() if paths else b''
                        if text.endswith(b'LOGGER_READY> '):
                            if count == 0 or b'SMALL_PARTIAL' in text:
                                break
                        time.sleep(.02)
                    else:
                        self.fail(f'{version}: partial line not available while running: {text!r}')
                run_terminal(version, commands=["printf SMALL_PARTIAL"], on_prompt=inspect)


if __name__ == '__main__':
    unittest.main()
