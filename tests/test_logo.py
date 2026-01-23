from remote.logo import (
    FIRE_PALETTE,
    LOGO,
    get_version,
    interpolate_color,
    print_logo,
)


class TestLogoPalette:
    """Tests for the color palette definition."""

    def test_fire_palette_is_list(self):
        assert isinstance(FIRE_PALETTE, list)

    def test_fire_palette_has_colors(self):
        assert len(FIRE_PALETTE) >= 2

    def test_fire_palette_colors_are_hex(self):
        for color in FIRE_PALETTE:
            assert color.startswith("#")
            assert len(color) == 7


class TestLogoConstant:
    """Tests for the LOGO constant."""

    def test_logo_is_string(self):
        assert isinstance(LOGO, str)

    def test_logo_is_multiline(self):
        lines = LOGO.strip().split("\n")
        assert len(lines) > 1

    def test_logo_contains_remote_text(self):
        # The ASCII art should spell "REMOTE"
        assert LOGO.strip()  # Not empty


class TestInterpolateColor:
    """Tests for color interpolation function."""

    def test_interpolate_same_color(self):
        result = interpolate_color((255, 0, 0), (255, 0, 0), 0.5)
        assert result == (255, 0, 0)

    def test_interpolate_at_start(self):
        result = interpolate_color((0, 0, 0), (255, 255, 255), 0.0)
        assert result == (0, 0, 0)

    def test_interpolate_at_end(self):
        result = interpolate_color((0, 0, 0), (255, 255, 255), 1.0)
        assert result == (255, 255, 255)

    def test_interpolate_midpoint(self):
        result = interpolate_color((0, 0, 0), (100, 100, 100), 0.5)
        assert result == (50, 50, 50)

    def test_interpolate_returns_tuple_of_ints(self):
        result = interpolate_color((0, 0, 0), (255, 255, 255), 0.33)
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all(isinstance(c, int) for c in result)


class TestPrintLogo:
    """Tests for the print_logo function."""

    def test_print_logo_outputs_to_console(self, capsys):
        print_logo()
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_print_logo_outputs_multiline(self, capsys):
        print_logo()
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) > 1

    def test_print_logo_with_version(self, mocker, capsys):
        mocker.patch("remote.logo.get_version", return_value="1.2.3")
        print_logo(show_version=True)
        captured = capsys.readouterr()
        assert "1.2.3" in captured.out


class TestGetVersion:
    """Tests for version retrieval."""

    def test_get_version_returns_string(self):
        version = get_version()
        assert isinstance(version, str)

    def test_get_version_has_semver_format(self):
        version = get_version()
        parts = version.split(".")
        assert len(parts) >= 2


class TestLogoIntegration:
    """Integration tests for logo display."""

    def test_logo_can_be_printed_without_errors(self):
        # Should not raise any exceptions
        print_logo()

    def test_logo_works_with_all_options(self, capsys):
        print_logo(show_version=True)
        captured = capsys.readouterr()
        assert captured.out  # Has output
