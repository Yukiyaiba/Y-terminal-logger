# Y-terminal-logger

[Magyar](#magyar) · [English](#english)

## Magyar

Meglévő telepítés frissítése: [UPGRADE_HU.md](UPGRADE_HU.md).

Interaktív Bash-terminálok helyi naplózása Linux alatt, Pythonból.
Új telepítéshez a **V2.0** változat javasolt; a V1.0 az egyszerű, egyfájlos
naplózási módot tartja meg. Egyszerre csak az egyik verziót telepítsd.

| Verzió | Funkció | Telepítés és beállítás |
| --- | --- | --- |
| [V1.0](V1.0/) | Egy szöveges terminálnapló munkamenetenként | [Útmutató](V1.0/README.md) |
| [V2.0](V2.0/) | Terminálnapló és Bash-history alapú parancsnapló, külön időbélyeges módokkal | [Útmutató](V2.0/README.md) |

Követelmények: Linux, Python 3.9+, Bash 5.1+, util-linux `script` 2.35+.
Külső Python-csomag nem szükséges. A macOS/BSD `script` nem támogatott.
Az alapértelmezett naplómappa mindkét verziónál `~/terminallogs`.

A naplók érzékeny adatokat tartalmazhatnak. Nincs titokszűrés vagy naplóforgatás,
és a szűretlen kimenet ideiglenesen lemezre kerül. Használat előtt olvasd el a
[biztonsági tudnivalókat](SECURITY.md). A TH a kimeneti bájtszámok alapján élőben követi a munkamenetet; nincs kilépésig
visszatartott szövegrész. A szokásos sorújrarajzolásokat kezeli, de nem teljes terminálemulátor.

Ellenőrzés a tároló gyökeréből:

```bash
bash -n V2.0/terminal_logger_hook.bash
python3 -m unittest discover -s tests -v
```

A tesztek ideiglenes mappákat és valódi pszeudoterminálokat használnak;
a saját `.bashrc` és history fájljaidat nem módosítják.
A mellékelt GitHub Actions munkafolyamat Linuxon futtatja őket.

Licenc: ebben a csomagban még nincs kiválasztott licenc. Nyílt forrású
kiadás előtt a jogtulajdonos adjon hozzá megfelelő `LICENSE` fájlt.

## English

Local logging of interactive Bash terminals on Linux, using Python.
**V2.0** is recommended for new installations; V1.0 retains the simpler
single-transcript mode. Install only one version at a time.

| Version | Features | Installation and configuration |
| --- | --- | --- |
| [V1.0](V1.0/) | One text transcript per session | [Guide](V1.0/README.md) |
| [V2.0](V2.0/) | Terminal transcripts and Bash-history command logs, with separate timestamped modes | [Guide](V2.0/README.md) |

Requirements: Linux, Python 3.9+, Bash 5.1+, util-linux `script` 2.35+.
No third-party Python packages are required. macOS/BSD `script` is unsupported.
Both versions default to `~/terminallogs`.

Logs may contain sensitive data. There is no secret redaction or log rotation,
and unfiltered output is staged in a temporary file. Read [SECURITY.md](SECURITY.md)
before use. TH follows output byte counts live, without withholding a trailing suffix until
exit. Common single-line redraws are handled; this is not a full terminal emulator.

Run the checks above from the repository root. Tests use temporary directories
and real pseudoterminals without changing your own `.bashrc` or history files.
The included GitHub Actions workflow runs them on Linux.

License: no license has been selected in this archive. Before an open-source
release, the copyright holder should add an appropriate `LICENSE` file.
