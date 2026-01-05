# Mac OS 7 Development Reference Blob and Cool Stuff I Made From It

Just in time for the 30th anniversary since System 7.5.3's Release on Jan 1996!

This repository contains a curated blob of reference material intended for use with LLM-assisted development of **Mac OS 7.x applications**, with **System 7.5.3** as a specific target.

The repository exists primarily to host these blobs; the **releases** is where all usable data for LLMS is located.

Check the technical_breakthroughs folder for tools, utilities and data that can supercharge your Classic Mac OS 7 tinkering. there's already a PNG to icon resource .r file tool there, sample input files and a sample output, as far as I am aware there is no comparable tool that makes this task this easy.

The second item that's been added is a nice little RS422 to RS232 adapter that goes well with a usb serial dongle, desktop COM port or router DB9 serial for PPP based networking of your old mac.

These assets can be unpacked into a Codex-style container.  
Typical install location:

    /opt

---

## Credits / Attribution

- **Apple Developer CDs**  
  Sourced from editions released in 1992, 1994, 1995, 1996  and 1997
  
  (12 discs total were required to make this work as well as this, it has benefitted from more delta data since the platform evolved substantially over time)

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

  His "Newton Keyboard Enabler" extension (project on github)
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

THE SCRIPT IS RELEASED, in technical_breakthroughs folder. I felt like I can't just hold on to this, it's too useful to keep to myself for other tinkerers who might want a less irritating toolchain and quicker turnaround on development.

---

## Intended Use

This repository, combined with an appropriate LLM-based coding tool, enables practical development of **Mac OS 7 applications**, with a strong focus on **System 7.5.3**.

The most obvious issues with it is that it can occasionally get stuck and insist on using a PowerPC API rather than a 68K one, experiments with Speech Manager were the first to reveal this issue with this blob, it's likely that an appropriate AGENTS.MD note will prevent this issue.
