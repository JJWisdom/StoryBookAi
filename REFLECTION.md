# Reflection - StoryForge

## Origin

I originally created this application for my Artificial Intelligence 101 class for my Master's program. At the time, the goal for that class was clear.

Create an application that turns text into clean PowerPoint slides, illustrated and captioned.

The grandiose idea was to create a presentation software that illustrated slides while the user was talking, but me and my project partner understood this was a stretch and massive overscope, so we pulled it back to something actually achievable.

That scoped-down version became the prototype. The full rewrite became StoryForge.

---

## The First Commit

The first commit was Haswell's part. We prototyped the concept together and he built the Tkinter UI from that. I was working on the Forge integration separately and offline, because it was too unstable and crash-prone to commit anything useful. It took long enough just to get Forge talking to Python that by the time it was working, the UI was already sitting in the repo. The first time both sides were actually connected was when the integration was stable enough to not immediately crash.

---

## Getting Forge to Work

Connecting Forge to the Tkinter frontend was the hardest part of the project. Two things that are not obvious and that I had to figure out: the API has to be explicitly enabled in ForgeUI settings, and you have to turn off the localhost popup it opens on launch or it gets in the way of the headless startup.

Forge's startup was also just inconsistent. Sometimes it was ready quickly, sometimes it would silently fail partway through loading. The startup detection in forge_handler.py ended up checking multiple things, polling the process, pinging the API endpoint, watching stdout. One check on its own was not reliable enough. I am not sure if there is a cleaner way to handle it, but that is what worked.

---

## Issues With the Original Code

There were several problems once I actually had something running.

- Threading issues. UI updates were happening on background threads and Tkinter is not thread-safe. The result was crashes that were hard to reproduce. The fix was routing UI state changes through self.after(0, ...) so they run on the main thread.

- The prompt transformer was not really a transformer. It produced prompts like "dragon, blew, fire, mountain, icy, blowing, storybook art style, masterpiece". Stable Diffusion needs more than that, composition, lighting, mood, context. A list of words stripped from a sentence does not give it that.

- ForgeHandler instances were getting created in multiple places and some got overwritten before being shut down. Forge would keep running in the background with nothing to kill it. I had to use Task Manager more than once.

- I accidentally committed the entire venv directory. 1,077 library files that should not have been there. I am still relatively new to using GitHub properly, most of my usage has been offline and local, and this was embarrassing. I caught it, cleaned it up, and added it to .gitignore. The commit message "Mistake made in commit" is still in the history. It stays.

These issues justified a rewrite of the key modules and an audit of what actually worked.

---

## The Claude Integration

Replacing the keyword transformer with the Claude API was the clearest improvement. A whole ten-slide storybook costs roughly $0.00003 on Haiku, fractions of a cent, and what comes back is something the model can actually work with instead of a bag of words.

The integration uses tool use rather than JSON parsing. Claude is forced to call one tool with a fixed schema, and the response comes back as a validated dict with the prompt, negative prompt, and a violation flag. No string parsing, no stripping markdown fences, no guessing which key the model decided to use. That cut out a whole category of problems I was having with parsing freeform responses.

The system prompt is also sent with caching turned on. It is the biggest fixed part of every call, so caching it means repeat calls do not pay full input cost each time.

Claude also does not prompt the same way for every model, but that is something the user sets, not something the app figures out on its own. There is a config switch between tag-style prompts for SD1.5 and anime models and natural-language prompts for SDXL, and the character budget changes with it. The two model types want different kinds of input, so I built the option in rather than forcing one format everywhere. The user picks the style that matches whatever model they loaded.

A couple of things I am glad I built in.

The app works without an API key. If no key is provided it falls back to the built-in keyword transformer. That kept things usable during development and means the core features still work for anyone without an Anthropic account.

The system prompt handles content safety. It includes an idiom exclusion list, because phrases like "died of laughter" or "scared to death" would trip a filter even though they are harmless in a children's story. Claude reads them by intended meaning. When something does get flagged, it separates accidental hits from deliberate ones and responds to each differently. An accidental hit gets a soft wholesome replacement image. A deliberate one gets a deliberately off-putting image instead. The safety check is part of the tool response, so the classification comes back structured rather than parsed out of text.

It also strips names, and that one was on purpose for accuracy, not safety. Stable Diffusion does not know what "Bob" looks like, so a name gives it nothing to work with and the character comes out inconsistent slide to slide. Claude replaces the name with a gender or species descriptor, "a man", "a small dog", so the model has something concrete to draw and the character stays consistent.

The failure handling is more careful than the original code ever was. Auth errors, rate limits, connection problems, and API errors are each caught separately with their own message, and some of them disable Claude for the session and fall back to the keyword builder. The user always sees what happened. Nothing fails silently.

---

## What I Would Do Differently

storybookgui.py ended up doing too much. Generation logic, UI logic, Forge lifecycle, config loading, publishing, violation handling, all of it ended up in one place because that was the easiest path as the project grew. Every bug fix was harder than it needed to be because everything was tangled together. If I started over I would keep the UI layer separate from the generation pipeline from the beginning, rather than trying to untangle them after the fact.

The cross-slide context passes every previous non-violation prompt to Claude to help keep characters and settings consistent. Slide 8 sees the prompts from slides 1 through 7. It works but it is rough. A better version would pull named entities from the story at the start and keep a running character sheet that updates as each slide is generated.

There are no automated tests. The core logic is testable and should have them. That is something I would do from the start next time.

I would also add a button to generate every slide at once. Right now you illustrate each slide one at a time. Even without proper multithreading, a single button that queues every slide and works through them would be a much better experience than clicking Illustrate over and over.

There is also a latent bug I know about. If the Claude API key dialog gets triggered while slides are being generated in the background, before you publish, while you are still editing, it fires on the wrong thread and crashes Tkinter. It has not come up in normal usage because the key is usually already set by then, but it is there. The fix is straightforward, just run the configuration check on the main thread before the background work starts.

---

## What This Project Is

StoryForge is a working local pipeline. Story text in, illustrated PDF out. It is not a polished product, the UI is Tkinter, setup requires a local Stable Diffusion install, and it only runs on Windows.

But it does what I set out to build, and the Claude integration actually works the way I wanted it to.