Framework dataset authoring guide

Audience: Sonnet in Claude Code, and Renee reviewing flagged files.
Scope: How to verify, author, wire, and version framework datasets under mcp/data/frameworks/.
Precedence: GLASSWING_SPEC.md governs. Where this guide and the spec disagree, the spec wins and you log the conflict in DECISIONS.md.

The one rule everything else serves: a classification pinned to a framework version must replay identically forever. Framework content is versioned data with effective dates. You never edit content in place, and you never assert a regulatory fact you have not verified against a primary source.


1. Verify before you author

Do this before writing a single field. No dataset gets authored or updated from memory or from a secondary summary.


Identify the primary source. For a statute or regulation, that is the enrolled bill text, the official code section, or the enforcing agency's final rule — not a law-firm client alert, not a vendor blog, not a Wikipedia summary. For a standard (ISO, NIST), the primary source is the published document from the issuing body.
Web-search the current status. Confirm four things: does it exist in the form you think it does, is it in force or pending, has its effective date moved, and has it been amended, superseded, or repealed since it was enacted.
Record what you found in verification_note: the source you checked, the URL, the date you checked it, and the finding in one or two sentences. If the finding is "in force, no changes since enactment," say that explicitly. If you could not reach a primary source, say that too — an honest "structure encoded from the official table of contents; clause text not independently verified" is worth more than a confident fabrication.
If verification changes an existing framework's status (a delay lands, a statute gets repealed), that is a new version, authored per section 5. You do not reach into the old file.


Status is relative to the date you check. A statute that is delayed today becomes enacted on its effective date with no content change. Record the as-of date in the note so the next reviewer knows when the status was true. The monthly framework-review procedure in the operator runbook is what catches these flips.


2. The versioned JSON file

Author to the structure already used by the three templates in mcp/data/frameworks/: eu_ai_act.json, nist_ai_rmf.json, colorado_sb_205.json. Open all three before authoring a new one — they show the field shapes and the tier/criteria nesting you are matching.

Required top-level fields

FieldTypeMeaningframework_idstring, stableLogical identity of the framework, stable across all versions (e.g. eu_ai_act). Pins resolve against this. Never changes for the life of the framework.namestringFull formal name, including the official citation (e.g. "General Data Protection Regulation (EU) 2016/679").descriptionstringOne paragraph: what it governs, who it binds, what triggers it. Neutral and factual.source_urlstringDirect link to the primary source you verified against.framework_versionsemver stringThe dataset version, not the law's version. Increment when you author a new file for this framework_id. Start at 1.0.0.content_dateISO dateThe date you authored or last verified this file's content.effective_fromISO date or nullWhen the obligations this file encodes begin to bind. Null only if genuinely not yet set.effective_toISO date or nullWhen this version stopped being the operative law. Null while it is current. Set when superseded, repealed, or replaced by a newer version.statusenumOne of enacted, delayed, amended, repealed. See section 6 for the decision rule.verification_notestringSource, URL, date checked, finding. Never empty.

Optional fields for the supersession case

Two pointer fields are not in the base template but are required when you model a statute that replaced or was replaced by another (section 7):

FieldMeaningsuperseded_byThe framework_id (and version, if known) of the instrument that replaced this one. Set on the old, repealed file.supersedesThe framework_id of the instrument this one replaced. Set on the new file.

Everything below the top-level fields — tiers, criteria, citation structures, attention triggers — mirrors the nesting in the three templates. Do not invent a new shape. If a framework genuinely does not fit the template shape, log the mismatch in DECISIONS.md and choose the closest fit rather than diverging silently.


3. Wire keywords into search_frameworks without breaking classifications

search_frameworks matches input text against per-framework keywords to decide which frameworks apply. Adding a new framework means adding keywords. The risk is that a keyword too broad captures fixtures that should only match existing frameworks, silently changing their citation sets.

The procedure:


Add keywords that are specific to the new framework. Prefer distinctive terms ("data subject," "DPIA," "controller") over generic ones ("data," "privacy," "user") that already-covered fixtures will trip on.
Keep the existing keyword blocklist intact. It carried over from v0.1 for a reason.
Run the golden regression suite (section 4) immediately after wiring.
Read the result honestly:

Suite still green: the keywords are scoped correctly. Done.
Suite red because an existing fixture's output changed, and it should not have: your keywords are too broad. Narrow them and rerun. Do not touch the golden files.
Suite red because an existing fixture legitimately now falls under the new framework: this is a real change to expected output, not a bug. Do not edit the golden file yourself. Flag it in the PR as a golden-fixture change requiring Renee's review, with the before/after and your reasoning. She approves the new golden, or she tells you the match is wrong.





A red suite is never resolved by quietly editing a golden file to match new output. The golden files are the contract. Either the code is wrong (fix it) or the contract changed (Renee ratifies it).


4. Run the regression that proves nothing broke

The proof that a new framework version did not disturb existing classifications is the golden suite passing with the new dataset present in the directory.

GLASSWING_OFFLINE=1 pytest tests/golden

This must run offline with pytest-socket active — no network, no API key, per the standing invariant. It classifies every golden fixture against the current dataset directory and compares tier, citation set, and human_review_required per framework against the frozen expected files.

Author the new framework, wire its keywords, then run this. Green means existing classifications replay identically under the change. If you also authored new fixtures that exercise the new framework, their expected outputs are new golden files that Renee reviews before they count as passing — a fixture that only proves the engine agrees with itself proves nothing.


5. Never edit in place — author new versions

When a framework's content or status changes, the existing file is frozen. You author a new file.


framework_id stays the same across versions. It is the logical identity that pins resolve against.
framework_version increments (1.0.0 → 1.1.0 for content additions, 2.0.0 for a status change or a substantive rewrite).
The new file is named to encode its version so both coexist on disk. Follow the repo's existing convention if one is established; if not, use <framework_id>.v<version>.json and log the convention choice in DECISIONS.md. The prior file is not renamed (renaming is an edit) — leave it and add the new one.
Set effective_to on the outgoing version to the date it stopped being operative. Set effective_from on the incoming version.


Framework selection at classification time resolves by framework_id plus the as_of_date: the engine picks the version whose effective window contains the classification date and whose status is in force. Old versions stay on disk so that any classification pinned to them replays exactly. Repealed and delayed versions remain on disk for replay but are excluded from new classifications by the effective-window-plus-status filter. You never delete a version file. Deleting one breaks the replay guarantee for every classification that used it.


6. Choosing status: enacted vs delayed vs amended vs repealed

Status is a property of the version, evaluated as of content_date.

StatusUse wheneffective_fromeffective_toenactedThe obligations are in force now. For a standard, the current published edition.in the pastnulldelayedPassed or published but not yet binding, or its effective date was pushed back. Still the operative instrument, just not yet enforced.in the futurenullamendedA later instrument modified this statute's text, but the statute persists under the same identity. The amendment is a new version of the same framework_id.unchanged from originalnull (still in force as amended)repealedThe instrument no longer has independent legal force — struck, sunset, or replaced by a successor with its own identity.as originally setthe date it ceased to have force

The line that trips people: amended vs repealed-and-replaced.


If the successor modifies the same statute (same statutory identity survives), it is an amendment. Author a new version of the same framework_id with status moving to amended on the prior version and the new version carrying the amended content.
If the successor repeals the old statute and enacts a new one (a new statutory identity), the old file is repealed and the new statute is a new framework_id with its own file. Link them with superseded_by / supersedes.


For a standard rather than a statute: enacted means the current published edition is in force; when a new edition supersedes it, the prior edition becomes repealed (superseded) with effective_to set to the new edition's publication date, and the new edition is a new version of the same framework_id.


7. Modeling a superseded-then-replaced statute

This is the Colorado case and the most error-prone pattern. Work it in this order.


Establish the legislative history from primary sources. Determine, and cite: did the original statute ever take effect, or was it repealed before its effective date? What is the successor's real citation and effective date? Does the successor amend the original or repeal-and-replace it? These facts decide the whole model, and you cannot infer them — verify each against the enrolled text or the legislature's bill history.
If it is repeal-and-replace (two identities): you produce two files.

The original keeps its framework_id. Status repealed. effective_to = the date it ceased to have force. superseded_by = the successor's framework_id. It stays on disk forever so any classification that used it replays.
The successor is a new framework_id with its own file. Its status is delayed if its effective date is in the future as of your content_date, or enacted if already in force. supersedes = the original's framework_id.



Handle the "repealed before ever effective" wrinkle. If the original was delayed, never took effect, and was then replaced, its effective_from and effective_to can be close or identical, and it may have zero classifications pinned to it. It is still repealed, still retained. Record in verification_note that it never took independent effect, so a later reviewer understands why the window is degenerate.
Do not let the successor inherit the predecessor's pins. They are separate framework_ids on purpose. A classification pinned to the old statute must never silently resolve to the new one. The as_of_date selection handles this correctly only because the identities are distinct — which is the reason repeal-and-replace is two files, not a version bump.



8. Worked example: adding GDPR as a new framework

GDPR is a clean case — long in force, no repeal, well-documented primary source. Use it as the template for any straightforward new-framework addition.

Step 1 — Verify. Search for the current status of Regulation (EU) 2016/679. Confirm: in force since 25 May 2018, not repealed, primary text on EUR-Lex. Note the check.

Step 2 — Author gdpr.v1.0.0.json (or the repo convention), matching the template shape:

json{
  "framework_id": "gdpr",
  "name": "General Data Protection Regulation (EU) 2016/679",
  "description": "EU regulation governing the processing of personal data of individuals in the EU. Binds controllers and processors. Triggered by processing of personal data, with heightened obligations for special-category data, automated decision-making with legal or similarly significant effects (Article 22), and large-scale or high-risk processing requiring a DPIA (Article 35).",
  "source_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
  "framework_version": "1.0.0",
  "content_date": "2026-07-09",
  "effective_from": "2018-05-25",
  "effective_to": null,
  "status": "enacted",
  "verification_note": "Verified against EUR-Lex primary text on 2026-07-09. In force since 2018-05-25, no repeal or superseding instrument found. Article 22 (automated individual decision-making) and Article 35 (DPIA) encoded as the classification-relevant triggers.",
  "tiers": [ "... mirror the criteria/citation nesting used in eu_ai_act.json ..." ]
}

Fill the tier and criteria structure from the template, encoding the classification-relevant provisions (Article 22 automated decision-making, Article 35 DPIA thresholds, special-category data under Article 9) with citations into the regulation.

Step 3 — Wire keywords. Add distinctive terms: "personal data," "data subject," "data controller," "data processor," "DPIA," "automated decision-making," "special category data." Avoid bare "data" and "privacy," which existing fixtures will trip on.

Step 4 — Regress. Run GLASSWING_OFFLINE=1 pytest tests/golden. Green means no existing fixture's classification shifted. If a fixture now legitimately implicates GDPR, that is a golden change for Renee to ratify, not one to make yourself.

Step 5 — Fixtures. Add new golden fixtures that exercise GDPR (a personal-data processing case, an Article 22 automated-decision case). Their expected outputs are new goldens pending Renee's review.


9. Bringing a flagged file to client-ready standard

Four files were authored under time pressure and flagged needs_owner_review. A flagged file is not client-ready until every substantive field traces to a verified primary source and its status modeling is correct. Below is what each named file needs. The same procedure applies to any other flagged file.

colorado_sb_205.json — a superseded-then-replaced statute

This is the section 7 pattern, and it is currently wrong if it models a single live statute. The reported history: the original Colorado AI Act (SB 24-205) was repealed and replaced by SB 26-189, effective 2027-01-01. Before accepting any of that, verify each fact against the Colorado General Assembly's bill history and enrolled texts, because the model depends entirely on the details:


Confirm SB 24-205's real fate. It had been delayed (reported to 2026-06-30). Determine whether it ever took independent effect or was repealed before its effective date, and cite the source.
Confirm SB 26-189's citation, its actual effective date, and — the decisive question — whether it amends SB 24-205 or repeals and replaces it. If it replaces, this is two framework_ids. If it amends, it is a version bump of one.
If repeal-and-replace: author the original as repealed with effective_to set and superseded_by pointing to the successor, and author SB 26-189 as a new framework_id, status delayed (its effective date is in the future as of now), supersedes pointing back. Record the never-took-effect wrinkle in the note if it applies.
Do not carry SB 26-189's obligations as though they bind today. Until 2027-01-01 it is delayed, and new classifications as of today should resolve to whichever instrument is actually in force now — which, if 205 is repealed and 189 is not yet effective, may be neither. If that is the finding, it is a real and important result, not a gap to paper over. Record it.


iso_42001.json — built from secondary commentary

This one may not be closable by web search alone, and that is the honest finding. ISO/IEC 42001:2023 is copyrighted and paywalled; blog summaries are not an acceptable source for client-ready content. To bring it to standard:


The classification-relevant structure (clause numbering, Annex A control list) must come from ISO's official published contents, not from commentary. If the full text is not accessible to you, encode only what the authoritative table of contents and control list support, and say so plainly in verification_note: "structure encoded from the official ISO/IEC 42001:2023 contents and Annex A control list; clause requirement text not independently verified against the standard."
Status is enacted (2023 edition is current), effective_from the publication date, effective_to null.
This file stays needs_owner_review until Renee, who can obtain the standard, verifies the requirement content against the actual text. Web verification cannot close it. Flag that limitation explicitly rather than presenting synthesized clause text as verified.


nyc_ll144.json — partially synthesized

This one is closable by web verification — the law and the enforcing rule are public.


Verify against the primary sources: NYC Local Law 144 of 2021 and the Department of Consumer and Worker Protection final rule. Confirm the bias-audit requirement for automated employment decision tools, the published-results requirement, and the candidate-notice requirement.
Nail the dates and note the distinction: the law's effective date and the enforcement start date differ (enforcement began 5 July 2023). Record effective_from as the enforcement date with a note explaining the choice, or carry both and document which the engine uses.
Status enacted. Replace any synthesized field with sourced content and update verification_note with the DCWP URL and check date. Once every field traces to the primary source, the flag clears.


The fourth flagged file

You named three flagged files but four were flagged. Confirm which fourth file carries needs_owner_review and apply the same standard: primary-source verification of every substantive field, correct status modeling per section 6, and an honest verification_note. If web verification cannot close it (as with ISO), say so and keep the flag.


10. Definition of done for any framework file


Every substantive field traces to a primary source cited in verification_note, with a check date.
status follows the section 6 decision rule and matches the verified legislative or publication history.
Supersession, if any, is modeled per section 7 with the correct number of framework_ids and the pointer fields set.
No existing file was edited in place; changes are new versions.
GLASSWING_OFFLINE=1 pytest tests/golden is green, or any golden change is flagged for Renee's ratification with reasoning.
Keyword additions are scoped narrowly enough that no existing fixture's output shifted unintentionally.
Anything you could not verify is disclosed in the note rather than presented as fact.