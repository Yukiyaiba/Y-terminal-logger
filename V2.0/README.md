# terminal-logger-V2.0

[Magyar](#magyar) · [English](#english)

## Magyar

Meglévő telepítés frissítése: [UPGRADE_HU.md](../UPGRADE_HU.md).

A V2.0 minden új interaktív Bash terminálhoz külön naplót hoz létre a **`~/terminallogs/`** mappában. Python 3.9+, Bash 5.1+ és a util-linux `script` 2.35+ parancsa szükséges. A naplófájlok jogosultsága 600. A TH mód élőben írja a kimenetet, kilépésig visszatartott szövegrész nélkül; az LBH bejegyzések közvetlenül a parancs előtt íródnak.

### Naplózási módok

A `terminal_logger.py` elején lévő változókkal állítható be a logok célmappája és a négy logolási mód kapcsolója, melyek egymástól függetlenül kapcsolhatóak (`True`/`False`):

```python
LOG_DIR = os.path.expanduser("~/terminallogs")
LOG_TERMINAL_HISTORY = True
LOG_TERMINAL_HISTORY_TIME_STAMPED = False
LOG_LIVE_BASH_HISTORY = False
LOG_LIVE_BASH_HISTORY_TIME_STAMPED = False
```

| Kapcsoló | Fájlnév vége | Tartalom |
| --- | --- | --- |
| `LOG_TERMINAL_HISTORY` | `-TH.log` | Szöveges termináltörténet |
| `LOG_TERMINAL_HISTORY_TIME_STAMPED` | `-TH-TS.log` | Ugyanez, soronként `YYYY-MM-DD HH:MM:SS ` előtaggal |
| `LOG_LIVE_BASH_HISTORY` | `-LBH.log` | A Bash előzménybe kerülő, beírt parancsok |
| `LOG_LIVE_BASH_HISTORY_TIME_STAMPED` | `-LBH-TS.log` | Ugyanezek a végrehajtás előtti másodpercre pontos időponttal |

Mind a négy mód futhat egyszerre. Ha mind a négy `False`, nem keletkezik napló. A fájlok neve `terminal_ESZKÖZNÉV_FELHASZNÁLÓ_YYYY-MM-DD_HH-MM-SS-UTÓTAG.log`. Egy másodpercben induló több ablak `_1`, `_2` stb. azonosítót kap az utótag előtt.

A TH módok szűrik a szokásos 7 bites ANSI vezérlőkódokat, és kihagyják az xterm alternatív képernyőt használó alkalmazások (például mc vagy btop) felületét. Más megjelenítési módot használó programnál a rajzolt felület bekerülhet. A TH-TS egy sor első naplózott darabjának idejét írja ki; az LBH-TS a parancs végrehajtásának kezdetét jelöli. Többsoros parancs esetén az LBH-TS időpontja a bejegyzés első sorára kerül.

**History-szabály:** A hook nem szinkronizálja az ablakok közös history-fájlját, és nem módosítja annak mentési beállításait.  A Bash `HISTCONTROL` és `HISTIGNORE` beállításait az LBH módok is követik. A saját Bash-beállításaidban megadott `HISTCONTROL=ignoreboth` mellett a szóközzel kezdődő és közvetlenül ismételt parancsok kimaradnak az LBH naplókból, de a TH naplókban látszanak.

### Telepítés

A két V2.0 fájl másolása után módosítsd a saját `~/.bashrc` fájlodat; a meglévő beállításaidat hagyd meg.

```bash
install -d -m 700 ~/terminallogs
mkdir -p ~/.local/bin
test -w ~/terminallogs && echo 'A naplómappa írható'
command -v python3
command -v script
install -m 755 /A/LETÖLTÖTT/terminal-logger/V2.0/terminal_logger.py ~/.local/bin/terminal_logger.py
install -m 644 /A/LETÖLTÖTT/terminal-logger/V2.0/terminal_logger_hook.bash ~/.local/bin/terminal_logger_hook.bash
cp -p --backup=numbered ~/.bashrc ~/.bashrc.backup-terminal-logger
nano ~/.bashrc
```

A `/A/LETÖLTÖTT/` helyére a kicsomagolt tároló szülőmappáját írd. Ha a `script` nem található: `sudo apt install util-linux`. A naplózót ne indítsd `sudo`-val.

A `~/.bashrc` elején meglévő interaktív ellenőrzés **után**, az előzménybeállítások után (nem szükséges konkrét `HISTFILESIZE` érték) illeszd be:

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

A fájl **legvégére**, az esetleges `PROMPT_COMMAND` beállítások után illeszd be:

```bash
if [[ ${TERMINAL_LOGGER_ACTIVE:-} == 1 ]]; then
  source "$HOME/.local/bin/terminal_logger_hook.bash"
fi
```

A korábbi V1.0 indítóblokkot és a régi `_terminal_logger_history_sync` blokkot távolítsd el, ha megtalálhatók. A meglévő `HISTCONTROL`, `histappend`, PS1, NVM és Deno sorok maradhatnak. Ellenőrzés után **új Bash-terminálablakot** nyiss:

```bash
bash -n ~/.bashrc
bash -n ~/.local/bin/terminal_logger_hook.bash
ls -lt ~/terminallogs | head
```

Próbához kapcsolj be minden módot, nyiss új ablakot, és futtasd: `echo naplóteszt`. Az ablakban négy külön fájl jön létre. A rejtett jelszóbevitel nem jelenik meg a TH naplóban; a látható szövegben és a parancssorban szereplő titkok bekerülhetnek.

### Eltávolítás

A `~/.bashrc` fájlból vedd ki a két V2.0 blokkot, vagy állítsd vissza a mentést. A meglévő naplók megmaradnak.

## English

V2.0 creates separate logs for every new interactive Bash terminal under **`~/terminallogs/`**. It requires Python 3.9+, Bash 5.1+, and util-linux `script` 2.35+. Log files use mode 600. TH writes output live without withholding a suffix until exit; LBH records are written immediately before each command.

### Logging modes

Near the beginning of `terminal_logger.py`, you can configure the log destination directory and four logging switches, which can be enabled or disabled independently (`True`/`False`):

```python
LOG_DIR = os.path.expanduser("~/terminallogs")
LOG_TERMINAL_HISTORY = True
LOG_TERMINAL_HISTORY_TIME_STAMPED = False
LOG_LIVE_BASH_HISTORY = False
LOG_LIVE_BASH_HISTORY_TIME_STAMPED = False
```

| Switch | Filename suffix | Content |
| --- | --- | --- |
| `LOG_TERMINAL_HISTORY` | `-TH.log` | Plain-text terminal transcript |
| `LOG_TERMINAL_HISTORY_TIME_STAMPED` | `-TH-TS.log` | Same transcript, with `YYYY-MM-DD HH:MM:SS ` on each line |
| `LOG_LIVE_BASH_HISTORY` | `-LBH.log` | Entered commands accepted into Bash history |
| `LOG_LIVE_BASH_HISTORY_TIME_STAMPED` | `-LBH-TS.log` | Same commands, timestamped to the second immediately before execution |

All four modes can run together. With all switches `False`, no log is created. Filenames follow `terminal_HOST_USER_YYYY-MM-DD_HH-MM-SS-SUFFIX.log`. Windows started in the same second share an additional `_1`, `_2`, etc. identifier immediately before the mode suffix.

TH filters common 7-bit ANSI control sequences and skips applications using the xterm alternate screen, such as mc and btop. Interfaces using other drawing methods may still appear. TH-TS timestamps the first logged chunk of a line; LBH-TS timestamps the command before it executes. For a multiline history entry, LBH-TS prefixes its first line.

**History rules:** The hook does not synchronize a shared history file or change history persistence settings.  LBH modes follow Bash `HISTCONTROL` and `HISTIGNORE`. With `HISTCONTROL=ignoreboth`, commands starting with a space and immediately repeated commands are omitted from LBH, though they remain visible in TH.

### Installation

After copying the two V2.0 files, edit your own `~/.bashrc` file; keep your existing settings.

```bash
install -d -m 700 ~/terminallogs
mkdir -p ~/.local/bin
test -w ~/terminallogs && echo 'Log directory is writable'
command -v python3
command -v script
install -m 755 /PATH/TO/terminal-logger/V2.0/terminal_logger.py ~/.local/bin/terminal_logger.py
install -m 644 /PATH/TO/terminal-logger/V2.0/terminal_logger_hook.bash ~/.local/bin/terminal_logger_hook.bash
cp -p --backup=numbered ~/.bashrc ~/.bashrc.backup-terminal-logger
nano ~/.bashrc
```

Replace `/PATH/TO/` with the parent directory containing the extracted repository. If `script` is missing, install it with `sudo apt install util-linux`. Do not run the logger with `sudo`.

After the existing interactive-shell check in `~/.bashrc`, add the startup block **after your history settings** (no particular `HISTFILESIZE` value is required):

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

Append this block to the **end** of `~/.bashrc`, after any other `PROMPT_COMMAND` settings:

```bash
if [[ ${TERMINAL_LOGGER_ACTIVE:-} == 1 ]]; then
  source "$HOME/.local/bin/terminal_logger_hook.bash"
fi
```

Remove any earlier V1.0 startup block and old `_terminal_logger_history_sync` block. Your existing `HISTCONTROL`, `histappend`, PS1, NVM, and Deno lines can remain. Check syntax and open a **new** Bash terminal window:

```bash
bash -n ~/.bashrc
bash -n ~/.local/bin/terminal_logger_hook.bash
ls -lt ~/terminallogs | head
```

For a quick test, enable all four modes, open a new window and run `echo logtest`; four separate files will be created for that window. Visible secrets in terminal output or command arguments may be logged. Hidden password input without terminal echo is absent from TH.

### Removal

Remove the two V2.0 blocks from `~/.bashrc` or restore its backup. Existing logs are retained.

## Korlátok / Limitations

- HU: A TH kezeli a szokásos soron belüli kocsivissza-, visszatörlés-, sortörlés- és vízszintes kurzormozgásokat. Az aktuális, még nyitott sort a fájlban frissíti, nem fűzi hozzá újra. Többsoros képernyőrajzolás, széles/összetett karakterek kurzorpozicionálása és más terminálprotokollok nem teljesen támogatottak. Az időbélyeges változatban a sor első szövegdarabjának helyi ideje marad meg.
- EN: TH handles common in-line carriage returns, backspaces, line erasure and horizontal cursor moves. The current open line is updated in place, rather than appended again. Multi-line screen drawing, cursor positioning with wide/combining characters and other terminal protocols are not fully supported. Timestamped lines retain the local time of their first text fragment.
- HU: A szűretlen kimenet ideiglenes, 600 jogosultságú fájlba kerül a rendszer ideiglenes mappájában (`TMPDIR`); mellette egy 600 jogosultságú timing fájl jelöli a tényleges kimeneti bájtszámokat, beleértve a kihagyott alternatív képernyőt is. Normál kilépéskor törlődik; összeomlás vagy kényszerített leállítás után megmaradhat. A törlés nem biztonságos adattörlés.
- EN: Unfiltered output is staged in a mode-600 temporary file in the system temporary directory (`TMPDIR`), alongside a mode-600 timing file describing actual output byte counts, including skipped alternate-screen content. Normal exit removes it; crashes or forced termination may leave it behind. Deletion is not secure erasure.
- HU: Nincs automatikus forgatás, tárhelykorlát, titkosítás vagy titokszűrés. A végleges és ideiglenes fájlok a munkamenet teljes ideje alatt nőhetnek. Saját felhasználói fiókhoz használd; nem auditbiztos naplózó. Részletek: [SECURITY.md](../SECURITY.md).
- EN: There is no automatic rotation, size limit, encryption or secret redaction. Final and temporary files can grow throughout the session. Use with your own account; this is not a tamper-proof audit logger. See [SECURITY.md](../SECURITY.md).
- HU: Linuxhoz és interaktív Bash-hoz készült; a macOS/BSD `script` nem támogatott. A grafikus terminál, SSH, tmux és a saját prompt-bővítmények együttműködését a saját környezetedben is próbáld ki.
- EN: Intended for Linux and interactive Bash; macOS/BSD `script` is unsupported. Verify your terminal emulator, SSH, tmux and prompt plugins in your own environment.
- HU: Az LBH az aktuális history-bejegyzést figyeli, nem teljes végrehajtási nyomkövetés. A history kikapcsolása vagy más bővítmények általi módosítása hiányzó bejegyzéseket okozhat. A parancs a Bash által historyba mentett alakban szerepel, nem feltétlenül bájtpontos bevitelként; a záró újsorokat a parancshelyettesítés elhagyja. Belső `bash -i` héjak ugyanazokat a naplókat használják, nem külön fájlokat.
- EN: LBH observes the current history entry, not every executed operation. Disabled history or other plugins modifying it can cause missing entries. Commands use Bash's history representation, not necessarily exact input bytes; command substitution removes trailing newlines. Nested `bash -i` shells share the current logs rather than creating separate files.
