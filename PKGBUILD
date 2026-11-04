# Maintainer: ppcharcoal
# Build & install from a clone of this repo:  makepkg -si

pkgname=tv-pad
pkgver=1.0.0
pkgrel=1
pkgdesc="Control the Wayland desktop with a gamepad while Sunshine streams it to the TV"
arch=('any')
url="https://github.com/ppcharcoal/tv"
license=('MIT')
depends=('python' 'python-evdev')
optdepends=(
  'wvkbd: on-screen keyboard (X button); from the AUR as wvkbd-git if not in the repos'
  'libnotify: on-screen notifications'
  'hyprland: pausing automatically while a game window has focus'
)
checkdepends=('python-evdev')
install=tv-pad.install
source=('tv-pad' 'tv-pad.service' 'LICENSE')
sha256sums=('SKIP' 'SKIP' 'SKIP')

check() {
  # The tests live next to this PKGBUILD in the repo clone.
  cd "$startdir"
  python -m unittest discover -s tests
}

package() {
  install -Dm755 tv-pad "$pkgdir/usr/bin/tv-pad"
  install -Dm644 tv-pad.service "$pkgdir/usr/lib/systemd/user/tv-pad.service"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
