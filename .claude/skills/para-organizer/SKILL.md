---
name: para-organizer
description: >
  Organizes files using Tiago Forte's PARA method (Projects, Areas, Resources, Archives).
  Applies official PARA classification rules, handles edge cases like tax documents and
  screenshots, asks before placing ambiguous files, and provides a post-organization summary.
  Use this skill whenever the user wants to organize files, folders, or a desktop into PARA.
---

# The Official PARA Skill for Claude
*by Tiago Forte - fortelabs.com*

When this skill is active, apply Tiago Forte's PARA method for all file organization tasks. Use the definitions, rules, and decision protocol below to classify every file correctly - especially the nuanced edge cases.

---

## What Is PARA?

PARA is a universal organizational system. Every piece of information belongs in one of four categories:

- **P**rojects - active work with a defined goal and end date
- **A**reas - ongoing responsibilities with no end date
- **R**esources - reference material organized by interest or topic
- **A**rchives - inactive items from the above three categories

The categories are ordered by actionability. Projects are the most actionable; Archives are the least. When classifying any file, always evaluate in this order: Project → Area → Resource → Archive.

---

## The Four Categories

### Projects

**Definition:** A project is a series of tasks linked to a goal with a deadline. It has a clear outcome you're working toward *right now*.

**Key test:** "Is this truly actionable right now, with a clear next step and a finish line?"

**Examples:** Course launch, book manuscript, tax filing, trip planning, legal agreement amendment, video production.

**Rules:**
- A project must have forward momentum - something is actively happening on it this week
- Keep projects focused: 5–10 items per project folder; break large projects into smaller ones
- Aim for 10–15 active projects total; work actively on 3–5 per week
- A "future project" is not a project - move it to Resources or Archives until it becomes active

**Critical edge case - financial/tax documents:** Tax documents, 1099s, financial statements, and similar files belong in a **Project** (e.g., "2025 Tax Filing"), not in an Area called "Finances." The deadline makes them actionable. Once taxes are filed, the project moves to Archives. The Area called "Finances" is for ongoing financial reference with no deadline.

**Critical edge case - context-specific files:** Any file clearly part of an active, named project - design assets for a course launch, screenshots captured for a video, a PDF related to a legal matter in progress - belongs inside that project folder, even if the connection isn't obvious from the filename alone.

---

### Areas

**Definition:** An area is a sphere of ongoing activity or responsibility with a standard to maintain over time and no end date.

**Key test:** "Is this something I maintain indefinitely, not something I finish?"

**Examples:** Health, Finances (general reference), Personal Development, Team Management, Home.

**Rules:**
- Areas have no completion date - if something has a deadline, it's a Project, not an Area
- Never use an Area as a catch-all for things that are actually active Projects
- Monthly or quarterly review cadence (vs. weekly for Projects)
- A file that's currently time-sensitive (e.g., a tax document approaching a deadline) should be elevated to a Project, not buried in an Area

---

### Resources

**Definition:** A resource is a topic or theme of ongoing interest that may be useful in the future but requires no action right now.

**Key test:** "Is this useful for future reference, but has no current action or deadline attached?"

**Examples:** Book notes, article clippings, code snippets, templates, research on a topic of interest, stock photos, design inspiration.

**Rules:**
- Organize by topic or interest, not by project
- No limit on the number of resource folders - collect freely
- Resources can become Projects later when they're assembled into something active

---

### Archives

**Definition:** Archives hold inactive items from Projects, Areas, and Resources - things no longer relevant right now but potentially needed someday.

**Key test:** "Is this truly no longer active, complete, or needed right now?"

**Examples:** Completed projects, ended relationships or roles, interests you've moved on from, outdated configs, memes, ephemeral screenshots, calendar noise.

**Rules:**
- Archives are not a graveyard - everything stays searchable and items can be reactivated at any time
- Organize alphabetically by folder; files reverse-chronologically by date
- Do NOT automatically archive screenshots or images - see the Screenshot Rule below

---

## Decision Protocol

When classifying any file, evaluate in this order:

1. **Does it clearly belong to an active, named Project?** → Put it there.
2. **Is it an ongoing responsibility with no end date?** → Area.
3. **Is it reference material with no current action needed?** → Resource.
4. **Is it ephemeral, complete, or no longer relevant?** → Archive.

When in doubt between two categories, default to the more actionable one. It's better to over-promote a file to Projects than to bury it in Archives where it won't surface.

---

## Screenshot and Image Rule

**Do NOT auto-archive screenshots.**

Screenshots are almost always captured for a reason. Before archiving any image or screenshot:

1. Can you determine what it shows - a tool, a product, a conversation, a moment?
2. Does it relate to any active project in the working directory?
3. Was it likely captured as documentation, evidence, or visual content for something?

If any of the above is unclear, **ask the user** before archiving. A screenshot that looks unimportant may be critical evidence, course content, or a captured idea the user needs.

Only archive a screenshot if it is clearly ephemeral - a calendar notification, a Reddit meme, a temporary confirmation screen with no ongoing relevance.

---

## Unreadable Files Rule

If you cannot read a file (encrypted PDF, unrecognized format, corrupted file, password-protected document):

- **Do not guess and silently place it.**
- **Ask the user.** Describe the file by name and type, then offer 2–3 plausible categories as a multiple-choice question.
- Let the user decide.

Example prompt: *"I wasn't able to read `statement_2024.pdf`. Based on the filename, it looks like it could be: (a) a financial statement → Projects/2025 Tax Filing, (b) a general financial record → Areas/Finances, or (c) something else. Which is right?"*

---

## When to Ask vs. When to Decide

**Always ask before placing when:**
- A file is ambiguous between Project and Area (especially anything financial, legal, or time-sensitive)
- A screenshot's purpose is unclear from its content
- A file cannot be read at all
- A file could plausibly belong to two or more active projects

**Decide without asking when:**
- The file's content clearly and unambiguously maps to one category
- The filename and content together leave no doubt
- The file is obviously ephemeral (a meme, a notification screenshot, a temporary download)

When in doubt, ask. A well-placed question is faster than correcting a misplaced file.

---

## After Organizing: Always Provide a Summary

When you finish organizing, always report:

1. **Count of items placed** in each category (Projects, Areas, Resources, Archives)
2. **Judgment calls** - any item where you made a non-obvious decision, flagged for the user to review
3. **Items you couldn't confidently place** - and what you need from the user to resolve them

This gives the user full visibility into your decisions and makes it easy to spot and correct the edge cases that require human context.
