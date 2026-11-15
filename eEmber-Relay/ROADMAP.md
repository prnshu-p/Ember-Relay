# Burning Activity Calendar: finalization roadmap

**Window:** Sat, Nov 14, 2026, 10:00 p.m. IST to Sun, Nov 15, 2026, 10:00 p.m. IST

**Team:** Member 1 and Member 2 (replace these labels with the team's actual names before relying on assignments)

**Submission target:** Sun, Nov 15, 2026, 10:00 p.m. IST

**Repository state:** the repository already has a substantial commit history. This document is the next planned commit, not the repository's first-ever commit.

## Working agreement

- Commit only work that has actually been completed and reviewed. Git timestamps must reflect when commits are made; do not backdate, fabricate a human-looking history, or split existing work into artificial commits.
- Keep the current uncommitted changes intact. Review and stage only the files for a coherent, validated change; do not use `git add -A` for the finalization commits.
- No push or publication is authorized by this plan. A public repository and accessible project links are stated as submission requirements in `SUBMISSION_FORM.md`; if the team cannot approve publication and verify the links, pause before submitting rather than claim they work.
- Member 1 owns data/model reproducibility and numerical claims. Member 2 owns the browser app, demo, and submission package. Both review the final release candidate and approve submission.

## Timeline and commit gates

| Time (IST) | Owner | Work and completion evidence | Commit checkpoint |
|---|---|---|---|
| Sat 10:00-10:20 p.m. | Member 1; Member 2 reviews | Add this roadmap, confirm the current branch and dirty-file list, and agree on owners. Do not modify or stage the existing work as part of this step. | **Now:** `docs: add finalization roadmap`. This is a real local commit of this file only. |
| Sat 10:20-11:15 p.m. | Member 1 | Inventory the uncommitted pipeline and experiment changes. Confirm every new experiment has a stated question, input/source, reproducible command, saved result, and a corresponding written conclusion. Identify blockers; do not commit merely to create activity. | No commit unless a discrete, verified correction is made. |
| Sat 11:15 p.m.-Sun 8:30 a.m. | Both | Stop work and rest. Leave the branch local; no scheduled overnight commits. | None. |
| Sun 8:30-9:00 a.m. | Member 2 | Reconfirm branch and working tree, review the overnight plan, and select the final candidate files. Agree on a short freeze list. | None. |
| Sun 9:00-11:00 a.m. | Member 1 | Reproduce the final model/independent-check results from the checked-in inputs and documented commands. Check E13-E15 scripts and outputs against their entries; reconcile any unsupported or absent claims. Run `python3 pipeline/test_static.py` if its dependencies and generated assets are present. | If results or tests require a real code/data correction, commit that coherent correction after review, e.g. `fix: correct verified validation issue`. Otherwise do not create a commit. |
| Sun 11:00 a.m.-12:00 p.m. | Member 2 | Run the frontend production build and lint (`cd frontend && npm run build && npm run lint`). Smoke-test country search, area selection, calendar-to-map interaction, charts, downloads, responsive layout, and browser console. Record failures and reproduce before changing code. | Commit only completed, reviewed frontend fixes: `fix: address final app QA findings`. |
| Sun 12:00-1:00 p.m. | Both | Break; keep the freeze list unchanged. | None. |
| Sun 1:00-2:30 p.m. | Member 1 | Audit numerical claims in `README.md`, `RESULTS.md`, `SUBMISSION.md`, and `SUBMISSION_FORM.md` against saved metrics and experiment outputs. Verify dates, units, uncertainty language, sensor names, limitations, and data credits. | If the text changes to correct verified facts, commit the docs as one reviewed unit: `docs: reconcile final results and limitations`. |
| Sun 2:30-3:30 p.m. | Member 2 | Rebuild/check slides and demo assets from the documented command. Verify media opens, names and links are correct, the project loads from a clean local clone/build where feasible. | Commit only regenerated, inspected deliverables: `docs: refresh final demo assets`. |
| Sun 3:30-5:00 p.m. | Member 1 + Member 2 | Cross-review one another's work. Run the final data/static checks and frontend build/lint again after any changes. Review `git diff --check`, inspect the complete staged diff, check secrets/large files, and verify no credentials or unintended raw data are included. | Commit only any remaining, specific defect fix; no omnibus commit just to empty the working tree. |
| Sun 5:00-6:00 p.m. | Both | Break and freeze features. Only submission-blocking defects may reopen code. | None. |
| Sun 6:00-7:30 p.m. | Member 2 | Walk through the submission form field by field. Verify project title, summary, credits, demo, repository, and live-app URLs. Test any URL that is already available in a private browser window. The checked-in form says the repository must be public and links must work without login. | Commit a real final wording correction if needed: `docs: finalize submission text`. |
| Sun 7:30-8:30 p.m. | Member 1 | Independently rerun the highest-risk checks and compare the reported headline numbers with the final artifacts. Verify the app's displayed figures/downloads and written claims still agree. | No commit unless an actual defect is fixed and retested. |
| Sun 8:30-9:15 p.m. | Both | Final go/no-go: no known blocker, clean successful checks, complete credits/disclosures, demo ready, both members approve. Decide separately whether public release is authorized. This plan itself does not authorize a push. | No ceremonial commit or tag. |
| Sun 9:15-9:45 p.m. | Member 2; Member 1 confirms | Complete the submission only if every required link is accessible and both members approve. If publication is not approved/possible or a required link is unavailable, stop and resolve that constraint with the organizers; do not submit inaccessible links as verified. | No commit unless a genuine last-minute correction is needed and revalidated. |
| Sun 9:45-10:00 p.m. | Both | Confirm the submission receipt/status, save the confirmation, and record any follow-up items. | End at 10:00 p.m. IST. |

## Release gates

1. **Scientific integrity:** every headline value traces to a reproducible output; validation scripts and results agree; caveats are retained.
2. **Data integrity:** source dates, filters, outage handling, generated assets, attribution, and exclusions are documented; no secrets or unreviewed large/raw files enter commits.
3. **Application integrity:** production build and lint pass; core interactions and exports work; no blocking browser errors or layout failures remain.
4. **Submission integrity:** descriptions match the shipped project; Data credits and methodology references are accurate; demo and required links open without login.
5. **Team approval:** both members review the final local diff and explicitly agree on submission and any later publication.

## Commands to use as applicable

```sh
python3 pipeline/test_static.py
cd frontend && npm run build && npm run lint
cd .. && git diff --check
```

Run the pipeline's expensive stages only if the underlying inputs, environment, time, and expected outputs are available; do not claim a stage passed if it was not run. Record failures and environment limitations for the team rather than masking them.
