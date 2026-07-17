from importlib.resources import files

from PySide6.QtGui import QImage, QImageReader


def test_production_atlas_is_v2_geometry() -> None:
    path = files("lion_cub_pet.assets").joinpath("spritesheet.webp")
    reader = QImageReader(str(path))
    size = reader.size()
    assert reader.canRead()
    assert (size.width(), size.height()) == (1536, 2288)


def test_left_gait_is_framewise_mirror_without_reordering() -> None:
    path = files("lion_cub_pet.assets").joinpath("spritesheet.webp")
    atlas = QImage(str(path))
    for frame in range(8):
        right = atlas.copy(frame * 192, 208, 192, 208).mirrored(True, False)
        left = atlas.copy(frame * 192, 416, 192, 208)
        assert right == left, frame


def test_custom_mode_frames_have_runtime_geometry() -> None:
    counts = {"relax": 8, "focus": 8, "sleep": 8, "motivate": 8, "advice": 8}
    root = files("lion_cub_pet.assets")
    for mode, count in counts.items():
        for frame in range(count):
            reader = QImageReader(str(root.joinpath(f"modes/{mode}/{frame:02}.png")))
            size = reader.size()
            assert reader.canRead(), (mode, frame)
            assert (size.width(), size.height()) == (192, 208), (mode, frame)


def test_smooth_standard_overrides_have_runtime_geometry() -> None:
    root = files("lion_cub_pet.assets")
    for state in ("idle", "wave", "jump", "waiting", "working", "review"):
        for frame in range(8):
            reader = QImageReader(str(root.joinpath(f"animations/{state}/{frame:02}.png")))
            size = reader.size()
            assert reader.canRead(), (state, frame)
            assert (size.width(), size.height()) == (192, 208), (state, frame)


def test_idle_closed_laptop_lid_remains_readable() -> None:
    root = files("lion_cub_pet.assets")
    for frame in range(8):
        image = QImage(str(root.joinpath(f"animations/idle/{frame:02}.png")))
        neutral_lid_pixels = 0
        for y in range(145, 208):
            for x in range(192):
                color = image.pixelColor(x, y)
                channels = (color.red(), color.green(), color.blue())
                average = sum(channels) // 3
                if (
                    color.alpha() >= 160
                    and max(channels) - min(channels) <= 50
                    and 45 <= average <= 225
                ):
                    neutral_lid_pixels += 1
        assert neutral_lid_pixels >= 2400, (frame, neutral_lid_pixels)
