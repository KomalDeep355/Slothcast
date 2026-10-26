# DEV post outline (writing quality is weighted most, so write this in your own voice)

Fill every [BRACKET] with a real number from `results/` or a real moment from your build. Delete anything you cannot back up.

1. **Hook (your story).** One concrete, specific moment where a deadline only became real at the last minute. Two or three sentences, no moral.
2. **The idea.** Not "stop procrastinating" but "learn how I slip, and make the next step smaller". Call the score *deadline risk*, not willpower.
3. **The lazy payoff.** What it saves you: [N seconds] of check-in per day, no manual planning, a [two-line] morning briefing.
4. **How it works.** The diagram from the README. One paragraph each: check-in + commits, features, TabPFN vs baselines, guardrailed Gemma plan.
5. **Why open mattered.** Run it with Wi-Fi off and show the network tab/empty egress. Say what stayed on your machine. Compare against a closed API you actually tried (cost, privacy, ability to swap models). Say "open-weight" for TabPFN, since the weights have a non-commercial license.
6. **Results, honestly.** Paste the table from `results/results.md` with [N] real days. Say whether TabPFN beat the baselines and whether the interval excludes zero. Show the calibration plot. Show the learning curve: how many days until it was worth trusting?
7. **What went wrong.** One real bug or surprise (a leakage test that caught you, a label you could not trust, an LLM output the guardrail rejected).
8. **Limits.** Small personal data, labels partly inferred, no behaviour-change test yet.
9. **Next.** The A/B week design.
10. **Demo.** Short screen recording on real data, plus the repo link.

Partner sections (only for tools you genuinely used, each with evidence): TabPFN (the evaluation), Gemma (the planner and guardrail), Temporal (a run that survived a killed worker), Sentry (a real trace and what it showed you), Entire/DevRelay (embedded session), .tech domain (live link).
