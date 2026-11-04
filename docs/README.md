# Preview assets

`screenshots/layouts.png` and `screenshots/appearance.png` are full-content
captures of the current plugin UI, including the stacked layouts and color
picker. The cover composes those unchanged captures with a title and subtitle.

Regenerate the cover from the repository root with librsvg:

```sh
rsvg-convert docs/preview.svg -o preview.png
```

The panel images are placed at their original pixel dimensions. Keep their
controls and labels unchanged when refreshing the screenshots.
