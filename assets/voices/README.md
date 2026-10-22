# Authorized reference audio

Preset filenames: `Warguy.wav`, `Kit_Laser.wav`, `Female.wav`. Supply clean speech only if you own it or have explicit permission for synthetic reproduction. Place an adjacent `Warguy.license.txt` (and corresponding preset names) recording owner, permission scope, date, and any attribution restrictions. Do not commit personal recordings to a public repository.

Names are user labels and do not assert a real person's identity or authorize cloning. The manual workflow currently uses neutral Piper speech and records this fallback in `voice_report.json`, even when a reference exists. To use references, run the optional Chatterbox backend with `--engine chatterbox` in a separately provisioned environment. Chatterbox is not installed in the lightweight default environment. Its CPU performance has not been benchmarked here. No Nano backend is claimed: a supported compatible implementation has not been verified.

Piper voice: en_US-ljspeech-medium, distributed by the Piper voices repository. Its MODEL_CARD is downloaded into the local models directory; review its license and upstream provenance before distribution. Code is GPL-3.0 to accommodate the GPL Piper runtime. The voice is a generic model preset, not an impersonation of any requested name.

The selected LJ Speech model card identifies the source dataset as public domain: https://keithito.com/LJ-Speech-Dataset/. Lessac was evaluated internally and replaced because its source recordings link to a research license. It is not the shipping voice. The output includes voice_model_card.txt.
