# Local SonarQube preview of PR #5 (not the SonarQube Cloud result)

SonarQube Cloud only reruns in GitHub after the push. To check the effect of `.sonarcloud.properties` before that, the files PR #5 changes were scanned on 2026-11-27 with the team's pinned local server and scanner (the images in `tests/team/run_sonar.py`, SonarQube 26.11).
The files were taken from the commit with `git archive`, so untracked folders such as `node_modules` were not included. There were two runs: without the exclusion, and with `-Dsonar.exclusions` set to the value in `.sonarcloud.properties`.

| Run | Files | Lines of code | Bugs | Code smells | Vulnerabilities / hotspots | Duplication |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| No exclusion | 29 | 57,655 | 127 | 52 | 0 / 0 | 74.0% (587 blocks) |
| `tests/team/rafay/evidence/**` excluded | 14 | 1,836 | 1 | 2 | 0 / 0 | 3.3% (4 blocks) |

Without the exclusion, 174 of the 179 issues were in generated reports (Playwright, Lighthouse and ZAP HTML/JS). After the exclusion, and after fixing the two `javascript:S8786` regex findings in `playwright.config.cjs`, 3 issues remain. All three are on unchanged upstream lines (`git blame`: upstream commit `ab7257a1`):

| Rule | Location | Assessment |
| --- | --- | --- |
| Web:InputWithoutLabelCheck (bug) | `resources/views/hardware/checkout.blade.php:165`, Notes textarea | False positive for the rendered page: the label comes from the `x-form.row` component (`<label for="note">`), and axe-core finds no label violation on the screen. Pre-existing upstream line |
| Web:S6825 (smell) | `resources/views/layouts/default.blade.php:1073`, `:1100`, modal close buttons with `aria-hidden` | Real, pre-existing upstream markup, outside the PR's changes |
| Duplication (4 blocks) | `resources/lang/en-US/general.php` | Upstream translation file; the PR adds one key |

A SonarQube Cloud pull-request analysis reports issues on new code only, so these upstream lines should not appear as new issues on PR #5. That must be confirmed in the SonarQube Cloud check after the push.
Raw output: `local-pr5-*-measures.json` and `local-pr5-*-issues.json`.
