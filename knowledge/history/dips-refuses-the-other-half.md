# "The other half of the census is dips, which no camera fixes" (session 116)

status: historical
Source: superseded by [../strategy/the-dip-budget-is-not-the-lever.md](../strategy/the-dip-budget-is-not-the-lever.md) (session 121)

Session 116 made `full_herd.lok_probe_key` a keep SHARE rather than a requirement on the endpoint set,
and gave two reasons. The first stands and is why the shape is still right: a camera term used as a
filter throws away firing states (session 73 measured 96% of them). The second is recorded here
because it was measured false, and because it was doing real work in the argument.

## Claim (dead): fixing the camera leaves ``dips`` refusing the other half

As written, in `lok_probe_key`'s docstring and carried into the truth page: "A KEEP SHARE, never a
filter: **the other half of the census is ``dips``, which no camera fixes**". The reading it invited -
that the camera axis is bounded above by a second clause waiting behind it, so making the camera
decisive could at best half-pay - is what session 121 measured directly.

## What the measurement says

Over all 402661 escape variants at the 99 endpoints of the uncapped cycle-3 census
(`_notes/s121_dips_census.py`):

- ``dips`` fails on 205281 variants, so the claim is true **as a count** and that is not the useful
  question;
- at the **53 endpoints that fire nothing**, ``dips`` is the SOLE refusal on **0** of their 200038
  variants, while `l_ok` fails on **all** of them and is sole on **55754**;
- relaxing `DIP_BUDGET` from 3 to 14 (the largest dip count observed) admits +39667 variants and
  revives **zero** endpoints - every dip-only refusal already sits at an endpoint that fires.

So there is no second clause waiting behind the camera at the endpoints the camera refuses. The 55754
`l_ok`-sole variants fire the moment it clears. ``dips`` co-occurs on 72% of the dead half's refusals
and decides none of them.

## Why it survived

``dips`` is a large number in every census that prints one, and `fires_census` reports ``fail``
alongside ``sole`` - the claim reads correctly off the ``fail`` column and incorrectly off the one
that matters. The sole column had been there since session 77.

The lesson is on the live page: **a clause that refuses a majority of variants is not thereby a lever;
what decides an axis is whether it is ever the last clause standing.**
