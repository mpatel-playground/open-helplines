# Open Helplines

**A free, open, source-cited directory of crisis and support helplines for every country, built so any app, website or AI assistant can show the right local number to someone who needs it.**

When a person tells a chatbot, a search box or a support app that they are in crisis, the reply should contain a real, working, *local* number. Today there is no good open dataset for that: lists go stale, and the most complete directories are proprietary. This project fixes that, one country at a time.

> **If you or someone else is in immediate danger, call your local emergency number now.**
> This project is a directory, not a crisis service.

## Use it

**Web:** <https://mpatel-playground.github.io/open-helplines/>

**JSON API** (static, free, no key, CORS-enabled via GitHub Pages):

| Endpoint | What it returns |
|---|---|
| [`/v1/index.json`](https://mpatel-playground.github.io/open-helplines/v1/index.json) | Every country with counts and emergency numbers |
| [`/v1/countries/GB.json`](https://mpatel-playground.github.io/open-helplines/v1/countries/GB.json) | One country (ISO 3166-1 alpha-2 code) |
| [`/v1/all.json`](https://mpatel-playground.github.io/open-helplines/v1/all.json) | Everything in one file |

```js
const res = await fetch("https://mpatel-playground.github.io/open-helplines/v1/countries/US.json");
const { helplines } = await res.json();
const suicideLines = helplines.filter(h => h.categories.includes("suicide"));
```

Or just copy `data/countries/*.json` (see the [JSON Schema](schema/country.schema.json) for consumers). The data is **CC0**: use it anywhere, no attribution required (though a link back helps people find and fix errors).

### What an entry looks like

```json
{
  "id": "gb-samaritans",
  "name": "Samaritans",
  "categories": ["suicide", "crisis", "mental-health"],
  "audiences": ["everyone"],
  "contacts": [{ "type": "phone", "value": "116123", "display": "116 123" }],
  "availability": "24/7",
  "cost": "free",
  "sources": [{
    "url": "https://www.samaritans.org/",
    "type": "operator",
    "accessed": "2026-11-24",
    "quote": "24 hours a day, 365 days a year. Call 116 123 for free"
  }],
  "status": "provisional",
  "last_verified": "2026-11-24"
}
```

### How much can you trust it?

Every number must be backed by a **source URL and a verbatim quote** from that source showing the number. Validation rejects any entry whose number is not in its quote.

- `provisional`: one source, normally the operator's own site or a government site.
- `verified`: at least two sources on different websites.
- `last_verified`: when someone last confirmed it. A weekly job re-fetches every source and opens an issue for anything that no longer matches.

If you are building something for people in crisis, consider showing only `verified` entries, or showing the `source` link next to `provisional` ones.

## Status

Early. A handful of countries are seeded; [most of the world is open for contribution](https://github.com/mpatel-playground/open-helplines/issues?q=is%3Aopen+label%3Acountry-data). See the [map of open tasks](https://github.com/mpatel-playground/open-helplines/issues).

## Contribute (humans and AI agents both welcome)

This project is deliberately set up so that AI coding agents can contribute safely alongside people: small, independent tasks, and machine-checkable rules.

- **AI agents:** read [`AGENTS.md`](AGENTS.md).
- **People:** read [`CONTRIBUTING.md`](CONTRIBUTING.md). You don't need to code; adding or checking one country's numbers is the most valuable thing you can do.
- **Found a wrong number?** [Report it](https://github.com/mpatel-playground/open-helplines/issues/new?template=report-wrong-info.yml). These are treated as urgent; see [`SAFETY.md`](SAFETY.md).

How the project is run, including the AI team lead, is described in [`GOVERNANCE.md`](GOVERNANCE.md).

## Run it locally

Python 3.9+ and nothing else.

```sh
python3 scripts/validate.py          # check the data
python3 -m unittest discover tests   # test the validator
python3 scripts/check_sources.py     # re-fetch sources (slow, needs network)
python3 scripts/build.py             # build dist/ (API + site)
```

## License

Data (`data/`): [CC0 1.0](DATA_LICENSE.md). Code: [MIT](LICENSE).
