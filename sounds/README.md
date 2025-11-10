# Timer Alert Sounds

This directory is reserved for custom alert sounds.

## Current Implementation

The timer alert currently uses **Windows built-in system sounds** which are always available and require no additional files:

- **Beep** - SystemAsterisk (information/asterisk sound)
- **Alert** - SystemExclamation (exclamation/warning sound)
- **Warning** - SystemHand (critical stop sound)
- **Question** - SystemQuestion (question dialog sound)
- **Default** - SystemDefault (system default beep)

These sounds are played via `winsound.PlaySound()` with the `SND_ALIAS` flag, which uses Windows' registered system sounds.

## Adding Custom Sounds (Future)

To add custom alert sounds in the future:

1. **Find MIT/Apache 2.0 licensed sound files** from sources like:
   - Freesound.org (filter by CC0/CC-BY licenses)
   - OpenGameArt.org
   - Archive.org
   - GitHub projects with compatible licenses

2. **Supported formats:** .wav files work best with winsound

3. **Naming convention:** Use descriptive names like:
   - `alert_gentle.wav`
   - `alert_urgent.wav`
   - `timer_beep.wav`

4. **Update code** in `widgets/timer_alert.py`:
   ```python
   SOUND_OPTIONS = {
       "Beep": "SystemAsterisk",
       "Custom Alert": str(Path("sounds/alert_gentle.wav").absolute()),
       # etc.
   }
   ```

## License Requirements

Any sound files added to this directory must use permissive licenses:
- ✅ MIT License
- ✅ Apache 2.0 License
- ✅ CC0 (Public Domain)
- ✅ CC-BY (with attribution in ATTRIBUTIONS.md)
- ❌ No GPL, CC-BY-NC, or proprietary licenses

## Attribution

If adding CC-BY licensed sounds, update `/ATTRIBUTIONS.md` with:
- Sound name
- Author/source
- License type
- Original URL
