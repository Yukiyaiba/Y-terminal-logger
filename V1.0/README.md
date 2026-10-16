# terminal-logger-V1.0

[Magyar](#magyar) · [English](#english)

## Magyar

Meglévő telepítés frissítése: [UPGRADE_HU.md](../UPGRADE_HU.md).

A V1.0 a korábbi egyfájlos naplózó működését tartja meg: minden interaktív Bash terminálablakhoz egy szöveges `.log` fájlt készít. A színező és kurzormozgató vezérlőkódokat eltávolítja, az xterm alternatív képernyőjét kihagyja. Nem készít külön parancsnaplót vagy időbélyeges változatot. Az alapértelmezett naplómappa `~/terminallogs/`. A naplómappa igény szerint a `terminal_logger.py` elején módosítható.

### Telepítés

Python 3.9+, Bash 5.1+ és a util-linux `script` 2.35+ parancsa szükséges. Az alábbiakat a saját gépeden futtasd; a forrás útvonalát igazítsd a letöltés helyéhez:

```bash
install -d -m 700 ~/terminallogs
mkdir -p ~/.local/bin
command -v python3
command -v script
install -m 755 /A/LETÖLTÖTT/terminal-logger/V1.0/terminal_logger.py ~/.local/bin/terminal_logger.py
cp -p --backup=numbered ~/.bashrc ~/.bashrc.backup-terminal-logger
nano ~/.bashrc
```

Ha hiányzik a `script`, telepítése: `sudo apt install util-linux`. A naplómappának a saját felhasználód számára írhatónak kell lennie. A `~/.bashrc` fájlban a már meglévő interaktív ellenőrzés után, az előzménybeállítások után (nem szükséges konkrét `HISTFILESIZE` érték) illeszd be:

```bash
if [[ $- == *i* && -z ${TERMINAL_LOGGER_ACTIVE:-} ]] && [[ -t 0 && -t 1 ]]; then
  python3 "$HOME/.local/bin/terminal_logger.py"
  terminal_logger_status=$?
  if (( terminal_logger_status == 0 )); then
    exit
  fi
  printf 'A terminálnaplózó leállt; ez a Bash naplózás nélkül folytatódik.\n' >&2
fi
```

Ellenőrzés: `bash -n ~/.bashrc`, majd nyiss új terminálablakot. Ne tedd be a V2.0 indítóblokkját is; egyszerre csak az egyik verziót telepítsd. A fájlok neve `terminal_ESZKÖZNÉV_FELHASZNÁLÓ_YYYY-MM-DD_HH-MM-SS.log`; az ugyanabban a másodpercben nyitott ablakok `_1`, `_2` utótagot kapnak. A fájlok jogosultsága 600. A látható titkok bekerülhetnek a naplóba.

### Eltávolítás

Töröld az indítóblokkot a `~/.bashrc` fájlból. Régi telepítésnél a `_terminal_logger_history_sync` blokkot is távolítsd el. A naplók megmaradnak.

## English

V1.0 preserves the behavior of the earlier single-log logger: it creates one plain-text `.log` file for each interactive Bash terminal window. It removes styling and cursor-movement control codes and omits the xterm alternate screen. It does not create a separate command log or a timestamped version. The default log directory is `~/terminallogs/`. The log directory can be changed near the top of `terminal_logger.py` if needed.

### Installation

Python 3.9+, Bash 5.1+, and the util-linux `script` 2.35+ command are required. Run the following commands on your own computer; adjust the source path to match where you downloaded the repository:

```bash
install -d -m 700 ~/terminallogs
mkdir -p ~/.local/bin
command -v python3
command -v script
install -m 755 /PATH/TO/DOWNLOADED/terminal-logger/V1.0/terminal_logger.py ~/.local/bin/terminal_logger.py
cp -p --backup=numbered ~/.bashrc ~/.bashrc.backup-terminal-logger
nano ~/.bashrc
```

If `script` is missing, install it with `sudo apt install util-linux`. The log directory must be writable by your user account. In `~/.bashrc`, insert the following block after the existing interactive-shell check and after your history settings (no particular `HISTFILESIZE` value is required):

```bash
if [[ $- == *i* && -z ${TERMINAL_LOGGER_ACTIVE:-} ]] && [[ -t 0 && -t 1 ]]; then
  python3 "$HOME/.local/bin/terminal_logger.py"
  terminal_logger_status=$?
  if (( terminal_logger_status == 0 )); then
    exit
  fi
  printf 'Terminal logger stopped; this Bash continues without logging.\n' >&2
fi
```

Check with `bash -n ~/.bashrc`, then open a new terminal window. Do not add the V2.0 startup block as well; install only one version at a time. Filenames follow `terminal_HOST_USER_YYYY-MM-DD_HH-MM-SS.log`; windows opened in the same second receive `_1`, `_2`, etc. suffixes. File permissions are 600. Visible secrets may be recorded in the logs.

### Removal

Remove the startup block from `~/.bashrc`. For older installations, also remove the `_terminal_logger_history_sync` block. Existing logs remain.

## Korlátok / Limitations

- HU: A TH kezeli a szokásos soron belüli kocsivissza-, visszatörlés-, sortörlés- és vízszintes kurzormozgásokat. Az aktuális, még nyitott sort a fájlban frissíti, nem fűzi hozzá újra. Többsoros képernyőrajzolás, széles/összetett karakterek kurzorpozicionálása és más terminálprotokollok nem teljesen támogatottak. Az időbélyeges változatban a sor első szövegdarabjának helyi ideje marad meg.
- EN: TH handles common in-line carriage returns, backspaces, line erasure and horizontal cursor moves. The current open line is updated in place, rather than appended again. Multi-line screen drawing, cursor positioning with wide/combining characters and other terminal protocols are not fully supported. Timestamped lines retain the local time of their first text fragment.
- HU: A szűretlen kimenet ideiglenes, 600 jogosultságú fájlba kerül a rendszer ideiglenes mappájában (`TMPDIR`); mellette egy 600 jogosultságú timing fájl jelöli a tényleges kimeneti bájtszámokat, beleértve a kihagyott alternatív képernyőt is. Normál kilépéskor törlődik; összeomlás vagy kényszerített leállítás után megmaradhat. A törlés nem biztonságos adattörlés.
- EN: Unfiltered output is staged in a mode-600 temporary file in the system temporary directory (`TMPDIR`), alongside a mode-600 timing file describing actual output byte counts, including skipped alternate-screen content. Normal exit removes it; crashes or forced termination may leave it behind. Deletion is not secure erasure.
- HU: Nincs automatikus forgatás, tárhelykorlát, titkosítás vagy titokszűrés. A végleges és ideiglenes fájlok a munkamenet teljes ideje alatt nőhetnek. Saját felhasználói fiókhoz használd; nem auditbiztos naplózó. Részletek: [SECURITY.md](../SECURITY.md).
- EN: There is no automatic rotation, size limit, encryption or secret redaction. Final and temporary files can grow throughout the session. Use with your own account; this is not a tamper-proof audit logger. See [SECURITY.md](../SECURITY.md).
- HU: Linuxhoz és interaktív Bash-hoz készült; a macOS/BSD `script` nem támogatott. A grafikus terminál, SSH, tmux és a saját prompt-bővítmények együttműködését a saját környezetedben is próbáld ki.
- EN: Intended for Linux and interactive Bash; macOS/BSD `script` is unsupported. Verify your terminal emulator, SSH, tmux and prompt plugins in your own environment.
