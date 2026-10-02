# Examples

Two storyboards that were rendered with the skill (motion engine, Piper narration):

| file | what | mode | formats | preset | length |
|---|---|---|---|---|---|
| `odd-squares.storyboard.json` | Why the first n odd numbers add up to n squared: equation reveal, dot layers, code, plot | lesson | 16x9 + 9x16 | chalkboard | ~52 s |
| `halving.storyboard.json` | Why binary search needs only ~20 looks for a million names | short | 9x16 | blueprint | ~36 s |

The durations in them are the ones measured from the narration grid. To try one:

```bash
S=~/.claude/skills/educational-video
$S/scripts/new_project.sh ~/videos odd-squares motion
cp examples/odd-squares.storyboard.json ~/videos/odd-squares/storyboard.json
python3 $S/scripts/validate_storyboard.py ~/videos/odd-squares --manifest
```

and ask Claude Code to continue from the narration phase, or read `skills/educational-video/SKILL.md`
and run the phases yourself. The `on` anchors name words in the scene's own narration.
