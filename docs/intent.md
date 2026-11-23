# Intent: brevkoll

Status: draft (first version drawn from the README and the v1 spec by an agent; the owner rewrites it in their own words,
then changes this line to `Status: accepted`. Agents read this file, cite it and never edit it.)

## Who it is for
Parents who are still learning Swedish and get letters from school, preschool and authorities: first my household, then
three international parents from the kids' school.

## The job
Photograph a Swedish letter and know, in my own language and in under a minute, what it says, what I must do and by when.

## Goals
- **G1** Read a letter in my language: a plain summary and a short list of what I must do.
- **G2** Never miss a deadline: every date in the letter reaches my calendar, with the letter's own wording beside it.
- **G3** Work on a phone with nothing to set up: no account, no install, usable from the browser.
- **G4** Make it obvious what to double-check: the answer says where the machine may be wrong (OCR, names, addresses).

## It must never
- **N1** Keep a letter: not stored, not cached, not logged, not recoverable after the request.
- **N2** Send a letter to a model I do not run myself. Names and street addresses are not redacted, so the model stays local.
- **N3** Let the model decide a date or a deadline. Dates come from code that reads the letter.
- **N4** Phone home: no analytics, no third-party scripts, fonts or images; the only outbound call is to my model.
- **N5** Sound surer than it is: no machine-read address, number or date is presented as verified.

## Out of scope for good
Accounts, history, storing letters, reminders and notifications, handwriting, becoming a general document assistant.
A request for any of these is a different app.

## How we will know it works
The household uses it for real letters for a month and prefers it to translating by hand. Kill date: 14 days after ship
(per the v1 spec), then decide to keep, change or drop it. `[owner to confirm and replace with your own measure]`
