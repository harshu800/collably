# Collably mascot assets

Drop image files here to be served from `/mascot/<filename>` on the frontend.

## Expected files

| Filename | Purpose |
|---|---|
| `collably.png` | Hero variant (full-body, winking, waving) — used on landing hero and 404 pages |
| `laptop.png`   | "Finding the right brands" — browse pages, empty-state for applications |
| `heart.png`    | "Happy creators" — successful-collab toast, testimonial section |
| `sunglasses.png` | "Big opportunities" — pricing / campaign browse highlights |
| `megaphone.png`  | "Let's collab" — invite/CTA blocks |
| `boba.png`     | Chill variant — settings, "nothing to do" empty states |

PNG with transparent background is preferred. SVG works if the source
export is clean. Keep each file under 500 KB for landing-page performance.

If you only have one combined composition image, save it as
`collably.png` for now — the frontend will reference the hero pose only
until additional poses are added.
