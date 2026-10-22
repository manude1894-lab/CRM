# Importing existing clients

Use `client-import-template.csv` to load the clients Triam already services into the CRM at go-live. New clients are not imported: they start as a prospect.

## How to import

1. Open the template in Excel, delete the two example rows and enter one client per row. Keep the header row unchanged.
2. Save as **CSV UTF-8**.
3. Sign in as an administrator → **Clients → Import CSV** → choose the file.
4. Check the preview. Rows marked *Duplicate* (a client with the same name exists) or *Error* are skipped; fix them in the file and import again. Rows already loaded are recognised and skipped.
5. Choose **Import**. Each client gets its Client ID from its Anchor Entity (e.g. `TMCL/00002`) and the next AML review is calculated from the risk rating and CDD completion date.

## Filling in the columns

| Column | What to enter |
|---|---|
| Company Name | Required. Legal name (for an individual, the full name). |
| Client Type | `Corporate` or `Individual`. Blank = Corporate. |
| Anchor Entity | Triam entity code: TCPL, TMCL, IFZA, TABL, TCDL or TBVI. Needed for the Client ID. |
| Non-anchor Entities, Services Obtained, Nature of Services Sought, Tags | Several values separated by `;`, written exactly as in Admin → Master Data. |
| Anchor RM (SPOC), Non-anchor RMs | The user's name as in Admin → Users (several non-anchor RMs separated by `;`). |
| Profile Status | `Active`, `Approved`, `Inactive`, `Marked for Exit` or `Exited`. Blank = Active. |
| Risk Rating | `High`, `Medium` or `Low`. |
| Dates | `DD/MM/YYYY`, e.g. `14/03/2019`. |
| Financial Year End | `MM-DD`, e.g. `12-31`. |
| Yes / No columns | `Yes` or `No`. |
| Country columns | As spelled in Admin → Countries, e.g. `United Arab Emirates (the)`. |
| Addresses | One column per part: Line 1, Line 2, Landmark, City, ZIP, P.O. Box, Country. |

Leave a column empty when the value is not known; it can be completed later on the client's page (changes to an approved client go through an amendment approved by Compliance).

## Not imported

Shareholders / UBOs, directors, authorised signatories, joint holders and documents are added on each client's page after the import.
