# Neonlight

Shopify theme for [Neonlight](https://www.neonlight.ch), a Swiss reseller of
custom LED neon signs for shops/businesses and for home decor.

Built on top of Shopify's [Dawn](https://github.com/Shopify/dawn) reference
theme (vendored, MIT-licensed — see `LICENSE.md`), with Neonlight branding
and a custom neon sign configurator layered on top.

## What's Neonlight-specific

- `sections/neon-configurator.liquid`, `assets/neon-configurator.css/.js` —
  the neon sign configurator stage (text/color/size selection is still to be
  built; currently shows the branded placeholder).
- `snippets/neonlight-logo.liquid`, `assets/neonlight-theme.css` — the
  Neonlight wordmark (N-icon tile + "NEONLIGHT", Syne font, glowing cyan
  accent bar) rendered in the header in place of Dawn's default text logo,
  plus the font override that swaps Dawn's heading font for Syne.
- `config/settings_data.json` — Dawn's five color schemes repainted to the
  Neonlight palette: dark schemes (`scheme-1`, `scheme-2`, `scheme-4`) on
  `#0B0C10`/`#111219` with a `#3FD7E0` cyan accent, light "print" schemes
  (`scheme-3`, `scheme-5`) on `#F7F3EC` with a `#1F8A91` teal accent.
- `templates/index.json` — homepage hero copy adjusted for the two target
  audiences (shops/businesses and home decor), with the configurator section
  placed between the hero and featured products.
- `templates/page.business.json` — a page template for a B2B "request a
  quote" page (pairs with Dawn's built-in `contact-form` section). Create a
  Page in Shopify Admin with the handle `business` for this to take effect.

## Still open (see the Neonlight launch roadmap for the full picture)

- The actual configurator UI (text/color/size selection with live preview).
- Real product data, photography, and collections for the two product
  lines (business signage vs. home decor).
- Content for the legal pages (Impressum, AGB, Datenschutzerklärung,
  Widerruf) — Dawn's default page template renders whatever content is
  entered for each Page in Shopify Admin, no template changes needed there.
- Payment/shipping configuration (TWINT, cards, invoicing for B2B) — set up
  in Shopify Admin, not in theme code.

## Working with this theme

This repo is theme code only; it isn't connected to a live Shopify store
from here. To preview or publish it, use the [Shopify CLI](https://shopify.dev/docs/themes/tools/cli)
from a machine with access to the store:

```sh
shopify theme dev    # local preview against the store
shopify theme push   # publish to the store
```

See `.github/dawn-README.md` for Dawn's own documentation (updating from
upstream, Theme Check, CI).
