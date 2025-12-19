# Mac OS 7 Development Reference Blob

This repository contains a curated blob of reference material intended for use with LLM-assisted development of **Mac OS 7.x applications**, with **System 7.5.3** as a specific target.

The repository exists primarily to host these blobs; the **one and only release** is where all usable data is located.

These assets can be unpacked into a Codex-style container.  
Typical install location:

    /opt

---

## Credits / Attribution

- **Apple Developer CDs**  
  Sourced from editions released in 1992, 1994, 1995, and 1996  
  (six discs total were required)

- **OpenAI / ChatGPT**  
  Assistance with heuristics and script creation used to collate the data  
  and extract as much raw text as possible from the developer CDs  
  (the extraction and curation process itself was performed manually)

- **Retro68**  
  https://github.com/autc04/Retro68/

- **Macintosh Garden**  
- **Macintosh Archive**

- **Markus Fritze**  
  https://github.com/sarnau  
  @sarnau  

  Provided icon delta data used during reverse analysis.  
  His software and all portions of it are subject to the **MIT License**;  
  a copy of the license may be found attached.

---

## Related Reference Project

https://github.com/sarnau/NewtonKeyboardEnabler

This project includes a code listing for a Rez `.r` file in its README that embeds icon data directly.

When combined with:

- Raw resource fork icon data
- PNGs generated from those resources using conventional tools
- Extracted documentation from the Apple Developer CDs

…it provided enough delta information to develop a **new Python script** capable of:

- Taking **six PNG files**
- Emitting a **Rez-compatible `.r` file**
- Producing icon resources compatible with **Retro68’s Rez**
- Correctly matching the **classic Mac OS color palette**

This script is currently pending release and is expected to be published, in its current form, within the next few uploads to this repository.

---

## Intended Use

This repository, combined with an appropriate LLM-based coding tool, enables practical development of **Mac OS 7 applications**, with a strong focus on **System 7.5.3**.

While the corpus is extensive, it currently lacks detailed documentation on certain finer points of **color-era Macintosh UI design**, particularly around:

- Colored UI controls
- Color usage conventions in system-era interfaces

There are known gaps in this area.

Despite this, the material has already enabled substantial progress on a personal project, which is intended for public release once it is ready.
