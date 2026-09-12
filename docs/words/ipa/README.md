# IPA lexicons

Source: [open-dict-data/ipa-dict](https://github.com/open-dict-data/ipa-dict)  
Format: `word<TAB>/ipa/` (variants comma-separated).

| File | Dialect | Use |
|------|---------|-----|
| `en_UK.txt` | British | **default** for Starlight (`fill_en_transcriptions.py`) |
| `en_US.txt` | American | optional via `--lexicon` |
| `fr_FR.txt` | French (France) | **default** for FR (`fill_fr_transcriptions.py`) |

```bash
# EN (Starlight)
python3 scripts/fill_en_transcriptions.py docs/words/json/starlight_6 --skip-pos phrase --overwrite

# FR (Loiseau / FR Trainer)
python3 scripts/fill_fr_transcriptions.py \
  docs/words/json/loiseau_blue_5 \
  docs/words/json/loiseau_blue_6 \
  docs/words/json/fr_trainer \
  --skip-pos phrase
```
