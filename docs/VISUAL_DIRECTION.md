# Visual direction — dynamic comparisons

The supplied population video demonstrates a continuously evolving bar-chart race: colored entries retain their identities, rank order changes, values advance, and a large year provides context. The supplied football video demonstrates a persistent two-column comparison with accumulating icon reveals. These are the design references for the new formats.

Implemented:

- **Race**: eight visible entries, country flags, persistent country colors, gradient bars, animated rank transitions, changing values and a large moving year. Source-derived leader changes become on-screen annotations. The ending reveals the latest observed leader.
- **Versus**: two anchored comparison panels, flags and country names, value counters, a proportional split bar, and person icons that accumulate as the source values change. Each icon's approximate unit is explicitly labeled. This format currently compares country statistics; it does not claim to know athlete trophy totals.
- **Sound**: original 124 BPM electronic score with synthesized kick, clap, hats, bass, plucks and pads. Ambient omits percussion; Cinematic uses half-time percussion. No audio is sampled from the references. Beat meters and reveal accents follow the score's tempo.
- **Readability**: fixed information plane, large type and source year, restrained background movement, no narration captions covering the graphics. No ninth row leaking under the race viewport.
- **Workflow**: Auto selects Race, or Versus when the brief contains “vs”/“versus”. Explainer retains the earlier speech-led format. Music-first formats skip speech models and Ollama entirely.

Annual data are retrieved from the World Bank. Intermediate numerical labels are explicitly interpolated between adjacent observed annual values. Missing data are never filled with zero or interpolated across a missing year. Visual rank positions transition between annual endpoint ranks; they should not be interpreted as exact intra-year rank observations. Dataset, source response and source metadata are included in every output.

This is a custom vector-style composition, not a copy of the reference footage, creator branding, athlete photos or soundtrack. Football trophies and other unrelated data domains still require dedicated, verified data adapters and suitably licensed assets.
