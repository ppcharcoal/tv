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
| **View + ↑** | wygaś / włącz monitor komputera (stream działa dalej) |
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

## Steam Big Picture

Gdy Sunshine streamuje aplikację ze „Steam” w nazwie (np. „Steam Big Picture”) albo na
pierwszym planie jest okno Steama lub gry ze Steama, pad zostaje w całości dla Steama:
tv-pad nie steruje myszą ani klawiaturą, działa tylko **View + ←** (koniec streamu).
Nazwę aplikacji przekazuje Sunshine (`SUNSHINE_APP_NAME`); `tv-pad status` pokazuje, co widzi.

Ustawienia: `watch_only_apps` (nazwy aplikacji w Sunshine), `watch_only_windows` (klasy okien),
`watch_only_combos` (kombinacje, które wtedy działają).

## Wygaszanie monitora (View + ↑)

Hyprland po wyłączeniu wyjścia (`dpms off`) przestaje renderować, więc stream by zamarzł.
Dlatego karta graficzna dalej rysuje obraz, a tv-pad tylko **ściemnia podświetlenie monitora
do zera** przez DDC/CI (`ddcutil`) i potem przywraca zapamiętaną jasność. Monitor cały czas
działa, więc zawsze da się go przywrócić. Nic nie zostaje na stałe: jasność wraca po ponownym
View + ↑, po zakończeniu lub wstrzymaniu streamu, po zatrzymaniu tv-pad, a nawet po awarii czy
odcięciu prądu (poziom sprzed ściemnienia jest zapisany w `~/.local/state/tv-pad/brightness`
i przywracany przy następnym starcie; jeśli jest nieznany, wraca 100%).

```bash
sudo pacman -S ddcutil
echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf
sudo modprobe i2c-dev
ddcutil detect                                  # powinno pokazać "Display 1"
ddcutil --brief getvcp 10                       # aktualna jasność, np. "VCP 10 C 70 100"
ddcutil setvcp 10 0; sleep 3; ddcutil setvcp 10 70    # test: ciemno i z powrotem
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
- Ręcznie: `tv-pad on`, `tv-pad off`, `tv-pad status`.
- Log: `journalctl --user -u tv-pad -f`.

## Testy

```bash
python -m unittest discover -s tests
```

Testy obejmują logikę przycisków, gałek i konfiguracji Sunshine, a także pełny przebieg demona
na symulowanym padzie (start streamu, mysz, kliknięcia, pauza dla gry, koniec streamu).

## Licencja

MIT.
