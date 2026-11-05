# tv-pad

Sterowanie pulpitem Linuksa (Wayland, Hyprland) padem, gdy komputer jest streamowany na
telewizor przez Sunshine i Moonlight. Lewa gałka to mysz, prawa gałka przewija, spusty
klikają, przyciski wysyłają skróty klawiszowe.

Działa **tylko podczas streamu**: Sunshine przy starcie streamu wywołuje `tv-pad on`, a przy
końcu `tv-pad off`. Poza streamem program czeka i niczego nie dotyka. Gdy na pierwszym planie
jest gra (Xbox Play, Steam, gamescope, RetroArch…), sam się wstrzymuje, żeby pad trafiał do gry.

## Instalacja (Arch)

```bash
git clone https://github.com/ppcharcoal/tv && cd tv && makepkg -si
systemctl --user enable --now tv-pad
tv-pad setup-sunshine
systemctl --user restart app-dev.lizardbyte.app.Sunshine.service
```

`tv-pad setup-sunshine` dopisuje do `~/.config/sunshine/sunshine.conf` (kopia zapasowa:
`sunshine.conf.bak`):

```ini
global_prep_cmd = [{"do": "/usr/bin/tv-pad on", "undo": "/usr/bin/tv-pad off"}]
```

Klawiatura ekranowa (przycisk X), opcjonalnie:

```bash
sudo pacman -S wvkbd || (cd /tmp && git clone https://aur.archlinux.org/wvkbd-git.git && cd wvkbd-git && makepkg -si)
```

Aktualizacja:

```bash
cd tv && git pull && makepkg -si && systemctl --user restart tv-pad
```

## Sterowanie

| Pad | Pulpit |
|---|---|
| lewa gałka | mysz (wolno przy lekkim wychyleniu, szybciej przy pełnym, przyspiesza po chwili) |
| prawa gałka | przewijanie (góra/dół i na boki) |
| A | lewy przycisk myszy (przytrzymanie = przeciąganie) |
| RT | Enter |
| LT | prawy przycisk myszy |
| L3 (wciśnięcie lewej gałki) | środkowy przycisk myszy |
| B | Esc |
| X | klawiatura ekranowa (pokaż/ukryj) |
| Y | Super+R (launcher aplikacji) |
| View (krótko) | Alt+Tab |
| **View + ←** | zakończ stream: monitor wraca, sterowanie padem gaśnie |
| Start + B | Super+C (zamknij okno) |
| LB / RB | Alt+← / Alt+→ (wstecz / dalej w przeglądarce) |
| **↓ + LB / RB** | poprzedni / następny workspace |
| **→ + LB / RB** | przenieś aktywne okno na poprzedni / następny workspace |
| krzyżak | strzałki (↓ i → wysyłają strzałkę po puszczeniu, bo mogą zaczynać kombinację) |
| przytrzymaj Xbox 1 s | pauza / wznowienie sterowania pulpitem |

Workspace'y są przełączane bezpośrednio przez `hyprctl dispatch` (tv-pad sam rozpoznaje starą
i nową, Lua, składnię). Skróty Super+R i Super+C muszą być ustawione w Hyprlandzie (np. `bind = SUPER, R, exec, wofi --show drun`,
`bind = SUPER, C, killactive`). Hyprland nie ma domyślnie Alt+Tab; przykład:

```ini
bind = ALT, TAB, cyclenext
bind = ALT, TAB, bringactivetotop
```

## Gry

Na czas gry pad należy do gry: tv-pad niczego nie wysyła na pulpit i nie przejmuje pada,
działa tylko **View + ←** (koniec streamu). Po zamknięciu gry sterowanie pulpitem wraca samo.

**Steam:** we właściwościach gry → *Opcje uruchamiania* wpisz:

```
tv-pad-game %command%
```

Jeśli gra ma już inne opcje, `tv-pad-game` dopisz na początku, np. `tv-pad-game gamemoderun %command%`.

**Inne programy:** `tv-pad-game polecenie [argumenty]`.

Okno klienta Steam to zwykły pulpit (można po nim klikać padem). Gry uruchomione bez
`tv-pad-game` też są rozpoznawane po klasie okna (`steam_app_*`, `gamescope`), ale tylko gdy mają
fokus. `tv-pad status` pokazuje, czy gra jest uruchomiona.

Ustawienia: `watch_only_windows` (klasy okien gier), `watch_only_combos` (kombinacje, które działają
w grze), `watch_only_apps` (aplikacje Sunshine traktowane jak gra).

## Monitor komputera podczas streamu

Gdy stream się zaczyna (także po wznowieniu), **monitor komputera robi się czarny**. Wybudza go
**dowolny klawisz na fizycznej klawiaturze przy komputerze** (USB albo Bluetooth). Nie wybudzają
go: klawiatura ekranowa, klawisze wysyłane padem przez tv-pad ani pisanie z telewizora przez
Moonlight. Po zakończeniu lub wstrzymaniu streamu monitor wraca sam.

Hyprland po wyłączeniu wyjścia (`dpms off`) przestaje renderować, więc stream by zamarzł.
Dlatego karta graficzna dalej rysuje obraz, a tv-pad przez DDC/CI (`ddcutil`) ustawia w monitorze
**jasność i kontrast na 0**. Monitor cały czas działa, więc zawsze da się go przywrócić.
Konfiguracji Hyprlanda tv-pad nie zmienia.

Jasność i kontrast monitor zapamiętuje u siebie, więc tv-pad przed wygaszeniem zapisuje poprzednie
wartości w `~/.local/state/tv-pad/brightness` i przywraca je: po wybudzeniu, po końcu lub pauzie
streamu, po zatrzymaniu tv-pad, a po awarii czy odcięciu prądu przy następnym starcie (jeśli jasność
jest nieznana, wraca 100%). Ręcznie: `tv-pad screen-on`.

Klawiatury są otwierane tylko na czas, gdy monitor jest czarny, wyłącznie do odczytu (naciśnięcie
trafia też normalnie na pulpit). Jeśli tv-pad nie ma do nich dostępu, monitor zostaje włączony
i pojawia się powiadomienie; wtedy:

```bash
sudo usermod -aG input $USER    # potem wyloguj się i zaloguj
```

Wyłączenie wygaszania: `"blank_on_stream": false` w `config.json`.

```bash
sudo pacman -S ddcutil
echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf
sudo modprobe i2c-dev
ddcutil detect                                  # powinno pokazać "Display 1"
```

Jeśli `ddcutil detect` pisze „Invalid display / DDC communication failed” przy działającym
monitorze, włącz **DDC/CI** w menu monitora.

> Nie używaj trybu zasilania DDC (`setvcp D6 05`): wiele monitorów (np. Acer) traktuje go jak
> wyłączenie przyciskiem i nie da się ich obudzić z komputera. Jeśli mimo to chcesz własne
> komendy, ustaw `"screen_mode": "commands"` oraz `screen_off_command` / `screen_on_command`.

## Kończenie streamu (View + ←)

Najczyściej przez API Sunshine: wpisz login i hasło panelu Sunshine do `config.json`
(`tv-pad config` tworzy plik):

```json
"sunshine_user": "twój_login",
"sunshine_password": "twoje_hasło"
```

Bez tego tv-pad restartuje usługę Sunshine, co też kończy stream (Moonlight pokaże zerwane
połączenie). W obu przypadkach monitor wraca, a sterowanie padem gaśnie od razu.

## Ustawienia

```bash
tv-pad config        # tworzy ~/.config/tv-pad/config.json z ustawieniami domyślnymi
systemctl --user restart tv-pad   # po zmianach
```

Najważniejsze opcje:

| Opcja | Znaczenie |
|---|---|
| `mouse_speed` | piksele na sekundę przy pełnym wychyleniu (domyślnie 1500) |
| `mouse_boost` | dodatkowe przyspieszenie po chwili pełnego wychylenia (2.0 = dwa razy szybciej) |
| `mouse_curve` | czułość przy małym wychyleniu (większa = precyzyjniej) |
| `scroll_speed` | ząbki kółka na sekundę przy pełnym wychyleniu |
| `deadzone` | martwa strefa gałek (0.14) |
| `swap_xy` | zamienia X i Y, jeśli sterownik pada zgłasza je odwrotnie |
| `pause_for_windows` | klasy okien (regex), przy których program się wstrzymuje |
| `osk_command` | klawiatura ekranowa (domyślnie `wvkbd-mobintl`) |
| `buttons`, `combos` | co robi każdy przycisk i kombinacja |

Akcje w `buttons` i `combos`:

- `"key:LEFTMETA+R"`: klawisze naciśnięte razem (nazwy jak w `linux/input-event-codes.h`, bez `KEY_`),
- `"mouse:LEFT"`: przycisk myszy (`LEFT`, `RIGHT`, `MIDDLE`, `SIDE`, `EXTRA`),
- `"osk"`: klawiatura ekranowa,
- `"cmd:polecenie"`: uruchomienie polecenia,
- `"none"`: nic.

Przykład: B jako „wstecz” w przeglądarce zamiast Esc i Start+A jako terminal:

```json
{
  "buttons": { "B": "key:LEFTALT+LEFT" },
  "combos": { "Start+A": "key:LEFTMETA+Q" }
}
```

Przyciski pomylone? `tv-pad test` pokazuje, jak program widzi każdy naciśnięty przycisk.
Jeśli X i Y są zamienione, ustaw `"swap_xy": true`.

## Jak to działa i ograniczenia

- Pad jest czytany z `/dev/input` (python-evdev), a mysz i klawiatura są wirtualne (uinput),
  więc działa w każdym kompozytorze Wayland. Dostęp do `/dev/uinput` zapewnia ta sama reguła
  udev co dla Sunshine.
- Podczas sterowania pulpitem pad jest „przejęty” (inne programy go nie widzą). W pauzie
  i w oknach z listy `pause_for_windows` jest oddawany.
- Sunshine wywołuje `tv-pad off` dopiero po **zakończeniu** aplikacji w Moonlight. Gdy stream
  jest tylko wstrzymany (wyłączony telewizor, wyjście z Moonlight), tv-pad rozpoznaje to po
  wpisach „CLIENT DISCONNECTED” / „CLIENT CONNECTED” w `~/.config/sunshine/sunshine.log`
  i oddaje pada, a po wznowieniu przejmuje go z powrotem. `tv-pad status` pokazuje, co widzi.
- Ręcznie: `tv-pad on`, `tv-pad off`, `tv-pad status`, `tv-pad screen-on`.
- Log: `journalctl --user -u tv-pad -f`.

## Testy

```bash
python -m unittest discover -s tests
```

Testy obejmują logikę przycisków, gałek i konfiguracji Sunshine, a także pełny przebieg demona
na symulowanym padzie (start streamu, mysz, kliknięcia, pauza dla gry, koniec streamu).

## Licencja

MIT.
