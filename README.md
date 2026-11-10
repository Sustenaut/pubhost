# pubhost

What makes a repository's sites and zones exist and stay right at the
outside systems that serve them: Terraform modules that turn `pubkit.json`'s
hosting block into DNS, mail, DNSSEC, Cloud Run and bucket resources at
Hetzner, Cloudflare, deSEC, Google Cloud and mailbox.org (`terraform/`); a
live check across a zone's nameservers (`pubhost dns check`); a reusable
workflow that applies a stack from CI (`terraform.yml`); and the actions that
build an image (`actions/docker-build`) and deploy a static site
(`actions/deploy-static`), which first runs `pubhost site check`.

What runs inside one repository about itself stays in
[pubkit](https://github.com/Sustenaut/pubkit): `pubkit sync`, which checks the
hosting block's shape, and the generated CI. Its `ci / site` job runs the
deploy-static the repository's own deploy workflow pins, in check-only mode,
and `job-service-terraform.yml` checks a stack without a backend.

    pubhost dns check ZONE [--record NAME/TYPE...]
    pubhost site check DIR [--url URL]
    pubhost --version

## Installing

The modules, the workflow and the actions are used from this repository by
commit, with the version in a comment:

    uses: Sustenaut/pubhost/actions/docker-build@<commit> # vX.Y.Z
    source = "github.com/Sustenaut/pubhost//terraform/hosting?ref=<commit>" # vX.Y.Z

The commit is the release tag's
(`git ls-remote https://github.com/Sustenaut/pubhost refs/tags/vX.Y.Z^{}`).

The command is a wheel. A repository that runs `pubhost dns check` lists it
beside pubkit in its `tests/requirements.txt`, and `pubkit lock` pins both by
sha256:

    pubhost @ https://github.com/Sustenaut/pubhost/releases/download/vX.Y.Z/pubhost-X.Y.Z-py3-none-any.whl

pubhost declares the oldest pubkit it works with (`pubkit>=` in
pyproject.toml); its own `tests/requirements.lock` pins the pubkit it is
tested with.

## What pubhost takes from pubkit

pubhost uses pubkit as a library for one thing: the hosting block's shape,
which `pubkit sync` checks and `pubhost dns check` reads. pubkit never
imports pubhost and names nothing of it; pubhost offers no `sustenaut.sync`
or `sustenaut.bump` hook, so pubkit never loads it into its own process.

These are all the names it takes, which `tests/features/pubkit.feature`
holds it to, and which the installed pubkit must have:

- `pubkit.hosting.settings`: the hosting block, checked.
- `pubkit.hosting.SEP` and `pubkit.hosting.dnskey`: a DNSKEY's key-signing
  flag and its parsing, for the pinned keys.

The modules' variable types are pubhost's, and the block's shape is pubkit's.
Both read `terraform/testdata/pubkit.json`: the modules' tests run on it, and
`tests/features/pubkit.feature` checks that pubkit accepts it and that every
setting it names is one `terraform/hosting`'s `config` declares.

`src/pubhost/site.py` stays standard-library only, because deploy-static runs
it from its own source with nothing installed. It carries a copy of pubkit's
`conform.exceptions`, marked as one, to read the site rules' exceptions.

## Hosting modules

Terraform modules for a repository's domains: their DNS, their email and
their sites, each at the provider the repository chooses, and the actions
that build an image and deploy a static site. They are taken from this
repository by commit, with the version in a comment, and they hold no provider's names, hosts or accounts: those are in the
repository's own `pubkit.json`, under `hosting`, so each repository keeps
its own setup.

### The hosting block

`providers` are the providers the repository uses, each under a name it
chooses, with a `type` and that provider's facts. `zones` are its domains,
each naming the providers that serve its DNS, its email and its sites.
This is [`terraform/testdata/pubkit.json`](terraform/testdata/pubkit.json),
which the modules are tested with (secrets never go here; tokens stay with
`./with-secrets`):

```json
"hosting": {
  "providers": {
    "hetzner": {
      "type": "hetzner",
      "dns": { "external_nameservers": ["helium.ns.hetzner.de.", "hydrogen.ns.hetzner.com.", "oxygen.ns.hetzner.com."] }
    },
    "cloudflare": { "type": "cloudflare", "account_id": "fedcba9876543210fedcba9876543210" },
    "desec": {
      "type": "desec",
      "dns": { "external_nameservers": ["ns1.desec.io.", "ns2.desec.org."] }
    },
    "gcp": {
      "type": "google-cloud",
      "project": "example-project",
      "region": "europe-north1",
      "cloud_run": { "domain_target": "ghs.googlehosted.com." }
    },
    "mailbox": {
      "type": "mailbox-org",
      "mx": ["10 mxext1.mailbox.org.", "10 mxext2.mailbox.org.", "10 mxext3.mailbox.org.", "10 mxext4.mailbox.org."],
      "spf": "include:mailbox.org",
      "dkim": { "mbo0001": "mbo0001._domainkey.mailbox.org.", "...": "..." }
    }
  },
  "zones": {
    "example.eu": {
      "dns": ["hetzner", "cloudflare"],
      "email": {
        "provider": "mailbox",
        "verification": { "f67e29eb00a65673481c0f9731bc90e0c6f94fd3": "<the key mailbox.org shows>" },
        "dmarc": { "policy": "none", "rua": "alerts@example.eu" }
      },
      "apex_txt": ["google-site-verification=abc"],
      "sites": {
        "@": { "provider": "hetzner", "kind": "server", "server": "web" },
        "blog": { "provider": "cloudflare", "kind": "pages", "project": "example-blog", "standby": "web" },
        "pub": { "provider": "gcp", "kind": "cloud-run", "service": "pub-site" }
      }
    },
    "example.net": {
      "dns": ["desec", "cloudflare"],
      "dnssec": {
        "keys": {
          "desec": ["257 3 13 Wegp...cvA=="],
          "cloudflare": ["257 3 13 o+F6...vBA==", "256 3 13 vowd...MAiQ=="]
        }
      },
      "sites": { "@": { "provider": "hetzner", "kind": "server", "server": "small" } }
    }
  }
}
```

The provider types pubkit supports, and what each holds:

| type | settings | serves DNS | sites |
| --- | --- | --- | --- |
| `hetzner` | `dns.external_nameservers`: the names Hetzner also serves a zone from, which a registrar such as Hetzner's own (konsoleH) lists next to another provider's; without them the registrar gets the assigned ones | yes; the zone must already exist at Hetzner | `server`: A (and AAAA) records to a server's addresses |
| `cloudflare` | `account_id` | yes; with another provider too, in multi-provider mode; signs with `dnssec` | `pages`: a Pages project (`project`; `subdomain` when Cloudflare gave it a pages.dev name other than `<project>.pages.dev`), served from Pages or, with `served_by: "server"`, from its `standby` server |
| `desec` | `dns.external_nameservers`: the names deSEC serves every zone from (`ns1.desec.io.`, `ns2.desec.org.`), which its API does not report | yes, through `terraform/desec-zones`; the zone must already exist at deSEC; always signs | no |
| `google-cloud` | `project`, `region`, `cloud_run.domain_target` (the host a custom domain's CNAME names) | no | `cloud-run`: a CNAME to `domain_target`, and a domain mapping to the Cloud Run `service` (`terraform/cloud-run-sites`) |
| `mailbox-org` | `mx` (`"priority host."`), `spf` (its mechanisms, such as `include:mailbox.org`), `dkim` (selector, in lowercase, to host) | no | no; a zone's `email.provider` |

A zone's `dns` lists the providers that serve its DNS, at most one of
each type; with more than one, every provider's nameservers are in the
apex NS rrset at each. Its `email` names a mail provider, with the domain's own
`verification` TXT records and `dmarc` (`policy` none, quarantine or
reject, and `rua`, where reports go). `apex_txt` holds other apex TXT
values, such as a Google site verification; they share the SPF record's
rrset, since Hetzner keeps one rrset per name and type. `sites` are by name
relative to the zone (`"@"` for the apex, which only a server site can
have, since the others are CNAMEs), each with its `provider` and that
provider's `kind`.

**DNSSEC.** A zone's `dnssec.keys` pins each of its DNS providers' public
keys, as DNSKEY values (`"flags 3 algorithm key"`, the key in base64
without spaces), by provider name. Every provider signs the zone with its
own keys and publishes the others' next to them (RFC 8901's multi-signer
model 2), so an answer from any of them validates against either DS
record at the registrar. Cloudflare's signing is turned on, with
multi-signer; deSEC signs every zone it serves. Each provider needs a
key-signing key (flags 257), and all keys one algorithm. Hetzner cannot
sign, so a zone it serves cannot have `dnssec`. The keys are pinned rather
than read from the providers: neither rotates them on its own, so a key
change is a reviewed change to `pubkit.json`. Cloudflare's are on its DNS
settings page, or `GET /zones/<id>/dnssec` (the KSK) and its DNSKEY rrset;
deSEC's are in `terraform/desec-zones`' output `keys`. Without `dnssec`,
Cloudflare does not sign.

**TTLs.** Records get a day for the apex NS rrset (written when two or
more providers serve a zone), an hour for the email records and the apex TXT
rrset, and five minutes for the sites, unless `ttl` says otherwise:
`hosting.ttl` for every zone, a zone's `ttl` for its records, or a site's
`ttl` (a number) for that site's; the nearest wins. Each is in seconds,
from 60 to a week. Lower them a TTL or more ahead of a change, so
resolvers pick it up sooner, and raise them again after.

```json
"hosting": {
  "ttl": { "email": 1800 },
  "zones": {
    "example.eu": {
      "ttl": { "sites": 60, "nameservers": 3600 },
      "sites": { "www": { "provider": "hetzner", "kind": "server", "server": "web", "ttl": 120 } }
    }
  }
}
```

A new provider of a known type is a new entry in `providers`; a repository
on two Hetzner projects names both. A new type, such as another mail
provider, needs pubkit to learn it once, in `src/pubkit/hosting.py`, and then
pubhost, in `terraform/hosting` (or a module beside it): a pubkit release,
then a pubhost release. Terraform ignores a setting its types do not name,
so `pubkit sync` (and `sync --check`, in CI) checks the block first and
stops on anything it does not know.

### Using it

The root module reads the block, gives the servers' addresses (known only
once the servers exist), and configures the Terraform providers, each with
the one account it deploys to. A repository with Cloud Run sites adds
`cloud-run-sites`:

```hcl
module "hosting" {
  source = "github.com/Sustenaut/pubhost//terraform/hosting?ref=<commit>" # vX.Y.Z
  config = jsondecode(file("${path.root}/pubkit.json")).hosting

  servers = {
    web = { ipv4 = module.web.ipv4, ipv6 = module.web.ipv6 }
  }
}

module "cloud_run_sites" {
  source = "github.com/Sustenaut/pubhost//terraform/cloud-run-sites?ref=<commit>" # vX.Y.Z
  config = jsondecode(file("${path.root}/pubkit.json")).hosting

  # When the services are created in the same apply.
  depends_on = [google_cloud_run_v2_service.pub_site]
}
```

A repository with zones at deSEC adds `desec-zones`, which writes the
same records there, and configures the deSEC provider with its token
(with `./with-secrets` and `"terraform.secrets": "declared"`, a
`DESEC_TOKEN` secret reaches it as `TF_VAR_desec_token`):

```hcl
variable "desec_token" {
  type      = string
  sensitive = true
}

provider "desec" {
  api_token = var.desec_token
  retry_max = 30
}

module "desec_zones" {
  source           = "github.com/Sustenaut/pubhost//terraform/desec-zones?ref=<commit>" # vX.Y.Z
  config           = jsondecode(file("${path.root}/pubkit.json")).hosting
  records          = module.hosting.records
  apex_nameservers = module.hosting.apex_nameservers
}
```

deSEC allows 15 rrset writes a minute (and 100 an hour) per domain, and
Terraform writes many at once, so a zone's first apply hits the limit. deSEC
then says how long to wait, and the provider waits that long before trying
again, up to `retry_max` times (5 by default, too few for a whole zone; 30
covers one of up to about 100 rrsets).

Its outputs are `nameservers` (by zone, for the registrar),
`cloudflare_zone_ids`, `records` (every rrset, by zone),
`apex_nameservers` (the apex NS rrset of each zone two or more providers
serve), `cloudflare_ds` (a signed zone's DS record at Cloudflare, for the
registrar) and `sites` (by full name: provider, kind, address, and a Pages
site's project and pages.dev name). `records` takes other rrsets, by zone,
for anything the block does not describe.

The modules need Terraform 1.11 or newer, `hcloud` 1.69, `cloudflare` 5.28,
`Valodim/desec` 0.6 and `google` 7. `terraform/hosting` needs no Cloudflare
token or provider block when no zone or site is at Cloudflare. The Google
and deSEC providers will not start without credentials, even with nothing
to do, so the Cloud Run domain mappings and the deSEC zones are in their
own modules, which only a repository on Google Cloud or deSEC takes.

- **`terraform/hosting`:** the block above, zone by zone: the records,
  the Pages projects and their domains, and each zone's DNS.
- **`terraform/cloud-run-sites`:** the Cloud Run sites' domain mappings,
  each to its `service` in its provider's `project` and `region`; output
  `domains`, with the records Google asks for.
- **`terraform/cloud-run-service`:** what every Cloud Run site repeats: the
  account it runs as, its registry (the ten newest images kept, older ones
  deleted after 30 days), and the service, behind IAP by default, on a
  placeholder image that Terraform ignores after the first deploy. Given
  `deploy_repository`, an account only that GitHub repository can act as,
  which can push to this registry and deploy this service and nothing else.
- **`terraform/backup-bucket`:** a private bucket with an age rule, and an
  account that can only create objects in it, with a key by default.
- **`terraform/cloud-run-access`:** who may pass IAP to each Cloud Run
  service, named rather than referred to, so it can be in another stack.
- **`terraform/desec-zones`:** each zone a `desec` provider serves: the
  domain, every rrset `terraform/hosting` writes (a TTL below the
  domain's `minimum_ttl` raised to it, as deSEC requires), the apex NS
  rrset when other providers serve the zone too, and with `dnssec` the
  other providers' keys; outputs `ds` (deSEC's DS records, by zone, for
  the registrar) and `keys` (its DNSKEY values, for `dnssec.keys`).
- **`terraform/dns-zone`:** one zone's rrsets in zone-file form (`name`
  relative, `"@"` for the apex; trailing dots, MX `"10 host."`, TXT
  quoted), at Hetzner, Cloudflare or both, with deSEC's nameservers when
  it serves the zone too. With more than one provider, Cloudflare runs in
  multi-provider mode: one unproxied record per value (MX split into
  priority and host), and every provider's nameservers in the apex NS
  rrset at each. Each record is keyed by its rrset and its value
  (`"nameservers ns1.desec.io"`, `"email_mx 10 mxext1.mailbox.org"`), so a
  value that comes or goes changes only its own record; A, AAAA and CNAME
  records, whose values may be known only after apply, keep their position
  (`"www 0"`). With `dnssec`, Cloudflare signs in multi-signer mode and
  serves the other providers' keys as DNSKEY records; denial of existence
  is left as Cloudflare's plan has it (NSEC on Free; RFC 8901 lets each
  provider choose). `terraform/hosting` calls it for each zone; it can be
  used on its own with `hetzner`, `cloudflare`, `desec` and `dnssec` set
  as in the block (`dnssec.keys` by provider type).
- **`actions/docker-build`:** builds a Docker image with buildx and a
  GitHub Actions layer cache, so an unchanged stage is restored instead of
  built again, and loads it into the runner's Docker for the job's checks
  and `docker push`. Give each image its own `scope`. A cached layer keeps
  the packages it was built with until something before it changes;
  `no-cache: true` takes the current ones.
- **`actions/deploy-static`:** deploys a directory to a server over rsync
  (`deploy-key`, `deploy-target`, and `known-hosts`, the server's pinned
  host key; without it the key is scanned on every run), to Cloudflare
  Pages (`cloudflare-api-token`, `cloudflare-account-id`,
  `cloudflare-project`, with wrangler pinned), or to both. It fails rather
  than deploy nowhere or to half a target. It runs `pubhost site check`
  (below) on the directory first and deploys nothing if that fails; give
  `site-url` so the check finds the og:image files, or `check: false` for
  a site that is not public.

  ```yaml
  - uses: Sustenaut/pubhost/actions/deploy-static@<commit> # vX.Y.Z
    with:
      dir: site
      cloudflare-api-token: ${{ secrets.CLOUDFLARE_PAGES_TOKEN }}
      cloudflare-account-id: ${{ vars.CLOUDFLARE_ACCOUNT_ID }}
      cloudflare-project: example-blog
      deploy-key: ${{ secrets.DEPLOY_KEY }}
      deploy-target: deploy@example.eu:./
      known-hosts: example.eu ssh-ed25519 AAAA...
      site-url: https://example.eu/
  ```

  Pin it as above, to the commit of a pubhost release, with the version in
  a comment; the site check it runs is that release's. pubkit's nightly
  moves a pin of this form to pubhost's latest release.

**Moving a zone that is already in use.** Hetzner made the apex NS rrset
with the zone, so the first apply with Cloudflare joining it must take it
over rather than create it, with an import block in the root module:

```hcl
import {
  to = module.hosting.module.zone["example.eu"].hcloud_zone_rrset.records["nameservers"]
  id = "example.eu/@/NS"
}
```

deSEC makes the zone's apex NS rrset too, so a zone it serves beside
another provider takes that over the same way, with the domain itself,
which must already exist at deSEC (created on desec.io):

```hcl
import {
  to = module.desec_zones.desec_domain.zone["example.eu"]
  id = "example.eu"
}

import {
  to = module.desec_zones.desec_rrset.records["example.eu nameservers"]
  id = "example.eu/@/NS"
}
```

Records a root module already manages, outside these modules, move with `moved` blocks, or with
import blocks like the one above when they were separate resources. In a
zone, the email records are `email_mx`, `email_dmarc`,
`email_dkim_<selector>` and `email_verification_<name>`, the apex TXT
rrset is `apex_txt`, and a site's are its name (`apex` for `"@"`, dots as
underscores), with `_a` and `_aaaa` for a server's addresses.

**Checking a zone.** `pubhost dns check ZONE` asks every nameserver of a
zone in the hosting block (its providers' from `pubkit.json`, the ones
resolvers find, and the ones each lists in its apex NS rrset), without
recursion, for every rrset the block describes (`--record NAME/TYPE` adds
others, such as a root module's own) and fails when their answers differ,
TTLs aside, or a nameserver does not serve the zone. With `dnssec`, each
nameserver must also serve exactly the pinned keys, and validate alone:
`delv` asks it for each rrset and for a name that does not exist, with
the pinned key-signing keys as trust anchors, as a resolver will once the
registrar has the DS records. When answers differ and one nameserver serves an older SOA serial than its provider's others (deSEC copies a change to ns2.desec.org a moment after ns1.desec.io), it says so: run it again in a minute. Run it after each step of a move, and
before any DS record goes to the registrar; it only reads, and needs
`dig` and `delv` (BIND 9; Debian's `bind9-dnsutils`).

Each module's tests (`terraform test` in its directory) mock the providers
and need no credentials; CI runs them on Terraform 1.11, with `fmt`,
`validate`, and the action's scripts under shellcheck and stubs.


### One stack per repository

A site's Terraform lives in the repository that owns its code, in `infra/`, with
its own state: one bucket, one prefix per repository (`prefix = "<repo>"`). What
every site shares (the project's APIs, the DNS zone, the Workload Identity
Federation pool) is in a base stack of its own. A site's stack never reads the
base's state, which holds keys: it reads the project and region from its own
`pubkit.json`, and finds shared things by their fixed names.

```hcl
locals {
  gcp = jsondecode(file("${path.module}/../pubkit.json")).hosting.providers["gcp"]
}

module "site" {
  source         = "github.com/Sustenaut/pubhost//terraform/cloud-run-service?ref=<commit>" # vX.Y.Z
  name           = "pub-site"
  project        = local.gcp.project
  project_number = "123456789"
  region         = local.gcp.region

  account_id           = "example-pub-site"
  account_display_name = "Example pub-site"

  deploy_repository = "example-org/pub-site"
}
```

`hosting` may list only `providers` here; the zones are the base's. The base's
pool must admit the repository, in its provider's `attribute_condition`, as this
module only makes the account the repository acts as.

**Moving a site out of a shared stack changes nothing in the cloud.** The site's
repository adds `infra/` with an `import` block for each existing resource, and
the shared stack replaces its file with `removed` blocks:

```hcl
removed {
  from = google_cloud_run_v2_service.pub_site

  lifecycle {
    destroy = false
  }
}
```

Both plans must show no change before either is applied: imports and removals,
with 0 to add, 0 to change, 0 to destroy. Apply the site's repository first, then
the shared stack, then delete the `import` and `removed` blocks. A write-only
secret version and a service account key do not survive an import unchanged: a
key's private half is not readable again, so leave those where they are, or move
the state itself.

## Terraform from CI

`terraform.yml` applies a Terraform stack from the default branch, as a
Google account it gets through Workload Identity Federation, so no key is
kept anywhere:

```yaml
name: terraform
on:
  push: { branches: [main] }
  workflow_dispatch:
permissions: { contents: read, id-token: write, pull-requests: read }
jobs:
  terraform:
    uses: Sustenaut/pubhost/.github/workflows/terraform.yml@<commit> # vX.Y.Z
    with:
      terraform-dir: infra
      workload-identity-provider: projects/123456789/locations/global/workloadIdentityPools/github/providers/github-terraform
      service-account: terraform-example@example-project.iam.gserviceaccount.com
    secrets: inherit
```

- Nothing runs until the repository variable `TERRAFORM_CI` is `on`, nor
  for any ref but the default branch. A first job, outside any environment,
  checks both.
- The `terraform` job runs in the environment `environment` names
  (`terraform`). Make it before `TERRAFORM_CI` is on, with its deployment
  branches limited to the default branch: GitHub makes an environment it
  does not find, open to every branch. GitHub Team allows that limit on a
  private repository; required reviewers there need Enterprise, so merging
  is what approves a change. Nothing runs for a pull request, so a pull
  request's code never runs with the account's credentials: plan it from a
  checkout first.
- Google trusts the job by its OIDC token's subject,
  `repo:OWNER/REPO:environment:terraform`, or
  `repo:OWNER@OWNER_ID/REPO@REPO_ID:environment:terraform` where the
  repository uses GitHub's immutable subjects (`gh api
  repos/OWNER/REPO/actions/oidc/customization/sub` shows which): the
  provider's condition and the account's `roles/iam.workloadIdentityUser`
  binding need nothing else, and a workflow that runs outside the
  environment gets no credentials.
- It plans to a file and applies exactly that file, one run at a time
  (concurrency group `terraform-<repository>`, never cancelled). The plan is
  in the job's summary; the file never leaves the runner. A plan that
  deletes anything, replacements included, is applied only when the pull
  request merged as that commit has the label `terraform-destroy`; either
  way the job lists what it deletes.
- Every run starts with a fresh `terraform init` against the backend the
  stack names. A provider download can fail (GitHub's release downloads,
  releases.hashicorp.com's SHA256SUMS), so init is tried three times, 15 s
  apart. With a provider mirror in pubkit.json, a fourth try installs every
  provider from it, through a CLI configuration with only its
  `network_mirror`; the module's `.terraform.lock.hcl` still checks each
  archive. The service CI's backend-less init does the same.

  ```json
  "mirror": {"terraform": "https://storage.sustenaut.eu/terraform"}
  ```
- With `secrets` (the default), each terraform command runs as
  `./pubsec run -- terraform -chdir=DIR ...`, with the environment's
  secret `BWS_ACCESS_TOKEN`, so the stack gets what `./with-secrets` gives it
  on a laptop. bws is the release's binary, checked against its sha256. With
  `secrets: false` terraform runs plainly and no token is read.

## Checking a public site

`pubhost site check DIR [--url URL]` reads a built site the way robots and
other sites do, so that search results, screen readers and link previews
(LinkedIn, Facebook, Slack, WhatsApp) get what they need. It reads DIR
only, never the network, and `deploy-static` runs it before every deploy.

| Rule | Checked |
|---|---|
| WEB-PAGE-01 | every page names its language, `<html lang>` |
| WEB-PAGE-02 | every page has a `<title>` and a `<meta name="description">` |
| WEB-OG-01 | every page has og:title, og:description, og:type, og:url (https) and og:image |
| WEB-OG-02 | og:image is an https address; one under `--url` is in DIR, a PNG or JPEG of at least 1200×627 (LinkedIn's large card) and under 5 MB, and matches og:image:width and og:image:height where given |
| WEB-OG-03 | every page has `<meta name="twitter:card" content="summary_large_image">` |
| WEB-ROBOTS-01 | robots.txt lets LinkedInBot, facebookexternalhit, Twitterbot and Slackbot read every page and its og:image: they obey it, so a `Disallow: /` meant for search engines hides the card too (keep a preview out of search with `<meta name="robots" content="noindex">` instead) |

Every `*.html` file is a page, except `404.html` and redirects (`<meta
http-equiv="refresh">`). A page that asks not to be indexed (`<meta
name="robots" content="noindex">`, in any case and alongside other values
such as `noindex, nofollow`, or `none`) is taken as not meant for search or
sharing, such as a service's bare landing page: it still needs its language
and title (WEB-PAGE-01, and WEB-PAGE-02's title), but not a description, a
card or an image, and robots.txt may keep the preview bots from it. A rule that a site cannot meet yet takes an
exception in `pubkit.json`, as the Rust crate standard's do (a rule, a
reason, an until date); `pubkit conform` reads only its own rules'.
The rules live in `src/pubhost/site.py` as `RULES`, one function per
family, so accessibility and other compliance checks join as new families.

LinkedIn keeps a link's card for about a week: after fixing a page, paste
its address into the [Post Inspector](https://www.linkedin.com/post-inspector/).

## Developing

    make venv         # the hash-locked environment, this checkout installed editable
    make check        # what CI runs: ./pubkit sync --check and the suite

`.github/workflows/hosting.yml` runs what the Python suite does not: each
module's `fmt`, `validate` and `terraform test`, the deploy-static scripts
under shellcheck with their stubs, actionlint on terraform.yml, and a
docker-build of a test image. `hosting / passed` is required on main beside
`ci / passed`.

Releases are pubrel's: a code change records what it changes (`pubrel add`),
and `pubrel prepare` cuts the release pull request. `wheel.yml` attaches the
wheel once main has tagged it.

## Licence

Apache-2.0.
