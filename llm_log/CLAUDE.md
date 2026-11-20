# CLAUDE.md -- logging rules (required by the course)

We used Claude Code for this project. Claude Code saves the full transcript of every session
automatically: every prompt, every response, every command it ran and its output.

1. Every session is recorded by Claude Code's automatic transcript. Nothing is summarised.
2. At the end of the project, each transcript is written into llm_log/LOG.md as a readable chat,
   with every prompt and every response in full.
3. LOG.md starts with a short index of every session: team member, tool, model and dates.
4. Never edit or delete existing entries in llm_log/.
5. Commit and push llm_log/ together with the final version of the code.
