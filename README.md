<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/neofetch-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/neofetch-light.svg">
  <img alt="neofetch" src="assets/neofetch-dark.svg" width="900">
</picture>

</div>

## OnBlitz

I build websites for local businesses that do not have one. A lot of good shops
near me are running on a Facebook page and a phone number, so I find them, build
them a real site first, and show it to the owner before I ever ask for anything.

Most of my time goes into the machine behind that rather than the sites themselves.

**Lead pipeline** &nbsp;·&nbsp; Python, SQLite<br>
Finds businesses with no site, then a fully deterministic enrichment pass digs
out a public email, phone and socials and scores how certain it is. Self-hosted
SearXNG and OpenStreetMap do the searching, so it runs at no cost per lookup, and
it refuses to attach a contact it cannot tie back to the business.

**Site builder** &nbsp;·&nbsp; Python, Jinja, static HTML<br>
Hand-written content specs compile into multi-page sites. Seven layout
archetypes, so two previews never come out as the same skeleton in different
colours, and an audit that fails a build for landing on a layout already in use.

**Control panel** &nbsp;·&nbsp; Node, no framework<br>
Runs on my phone. Leads on a map, call sheets that know each business's own
timezone and opening hours, the Instagram inbox, a file browser, and agents I can
start and steer from anywhere.

**Remote access** &nbsp;·&nbsp; Cloudflare tunnel, Guacamole, Tailscale<br>
A gateway with its own auth in front of all of it, plus an RDP desktop and a
terminal in the browser, so the whole thing is usable from a locked-down
Chromebook on a school network.

## Projects

| | |
| --- | --- |
| **OnBlitz** | The business and everything above. [onblitz.net](https://onblitz.net) |
| **[Pi-PhoneViewer](https://github.com/Zernic/Pi-PhoneViewer)** | Raspberry Pi image that lets you plug in any device and use it remotely |
| **PostBolt** | 30-day social media planner for small businesses. TypeScript |

## Reach me

[onblitz.net](https://onblitz.net) &nbsp;·&nbsp; onblitzdesign@gmail.com

<sub>The card up top is not a screenshot. <a href="scripts/neofetch.py">scripts/neofetch.py</a> rebuilds it from the GitHub API every Monday.</sub>
