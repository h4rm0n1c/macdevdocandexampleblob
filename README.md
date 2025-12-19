I just needed that horrid "new repo" screen to go away.
This is a blob of useful data that codex can use to help you develop mac os 7 apps.
the one and only release is where the blobs are located.
these can be unpacked into a codex container, I usually put them in /opt


Credits/Attribution
Apple Developer CDs from 1992, 1994, 1995 and 1996 (I only needed 6 total)
OpenAi/ChatGPT for assistance on heuristics/script creation to collate the data (this process was done manually) and extract as much raw text data as possible from the above developer CDs.
Retro68 - https://github.com/autc04/Retro68/
Macintosh Garden and Macintosh Archive.

https://github.com/sarnau/NewtonKeyboardEnabler 
 This project has a code listing for a .r file in its readme with icon data inside it.
 Combined with the raw resource files and some PNGs made from them with conventional tools, this provided enough delta data along with the above developer docs to create a new python script that
 can take 6 PNG files and produce a .r file that Retro68's Rez can use, matched to the Mac OS color pallette. this script is pending release and will likely be released in its current form within the next few uploads to this repo.

 This repo + an approrpriate LLM coding tool can enable one to write Mac OS 7 apps, with 7.5.3 as a specific target.

 It currently lacks more detailed documentation on the finer points of colored UI design/color UI controls from the color era of macs unfortunately, there are some holes, but I've managed to use this to make some pretty amazing progress in a personal project that I intend to release when ready.
