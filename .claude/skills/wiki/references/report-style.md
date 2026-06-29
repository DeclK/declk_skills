# Report Style

Write reports for fast onboarding:

1. Start with the architecture in 5-10 bullets.
2. Show top-level directories and their responsibilities before individual files.
3. Put entrypoints early, with commands/signals.
4. For connections, show `uses` and `used by` for key files only.
5. Include key files recommended for deep reading and explain why they were selected.
6. Describe repeated directories at directory level and list representative sample files instead of summarizing every file.
7. Include Mermaid or DOT graph snippets only for directory/core/neighborhood views, not dense full graphs.
8. Include a suggested reading order.
9. Keep uncertainty explicit: dynamic imports, factory patterns, runtime registration, monkey patching, and config-only links may be incomplete.
10. Avoid dumping all graph edges into prose. Link to JSON artifacts for exhaustive data.
