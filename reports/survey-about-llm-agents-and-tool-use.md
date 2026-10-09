# Survey about LLM Agents and Tool Use

## TL;DR
- Recent advancements in LLM architectures enhance their effectiveness and applications in diverse scenarios, particularly in detecting deception [1].
- The concept of seamless tool integration exhibits significant potential but also exposes LLM agents to vulnerabilities [2]. 
- A comprehensive evaluation of LLMs focusing on epistemic humility reveals how uncertainty and conflict management could influence their reliability [3].

## Background
LLM agents, or large language model agents, represent a paradigm shift in the application of AI, where models not only generate language but also assist in task execution and decision-making. As these agents have become integral to various applications, understanding their architectures, interaction with tools, and outcomes in real-world scenarios has become increasingly important to ensure their efficacy and safety.

## Core Architectures of LLM Agents
The latest studies underline the importance of advanced probes in LLM architectures that improve deception detection capabilities, achieving remarkable accuracy rates [1]. The implementations of real-time monitoring systems further enhance the operational reliability of these agents by allowing for immediate interventions to correct undesirable behaviors [4]. Furthermore, the analysis of epistemic humility within agents highlights how conflicting evidence can lead to suboptimal decision-making processes, which needs to be addressed for enhancement [3]. 

## Utilization of Tools by LLM Agents
LLM agents demonstrate innovative tool utilization strategies facilitated by frameworks such as Tool-R0, which enables agents to learn through self-play and significantly adapt without pre-existing datasets [2]. Despite advancements, this integration raises security fears as the autonomous actions of these agents can lead to potential exploits and unintended consequence [5]. Through autonomous hacking capabilities, LLM agents show that while they can perform complex tasks effectively, their deployment comes with major risks [2].

## Benchmarks and Applications
In real-world settings, LLM agents have shown considerable promise in various domains from automation to deception detection [6]. However, significant challenges persist around the vulnerabilities and uncertainties involved in their operational capacities that prompt rigorous benchmarking efforts to mitigate risks [7]. Moreover, methods for generating challenging training examples for tool-using agents have been proposed, reminding developers of the necessity for continuous improvement and vigilance [8]. 

## Trends and Open Problems
Over the last two years, LLM agents have exhibited significant growth in both adaptability and application areas. The ongoing concerns about security vulnerabilities and efficiency related to tool use in LLMs remain unaddressed in many systems, thus identifying these areas as open problems needing further exploration and solution-oriented research [9]. Given their increasing deployment in tasks that require high reliability, the assessment of ethical and operational frameworks will be critical as we advance [10].

## References
[1] Caught in the Act: Probes Effectively Detect Sabotage and Catch Unverbalized Deception. arxiv. https://arxiv.org/abs/2610.12445 (2026-10-08)
[2] Executable Code Actions Elicit Better LLM Agents. hf-search. https://huggingface.co/papers/2402.01030 (2024-02-01)
[3] Accurate but Not Humble: Evaluating Epistemic Humility in LLM Agents under Knowledge Conflict. arxiv. https://arxiv.org/abs/2610.12360 (2026-10-08)
[4] OnTrack: Real-Time Monitoring and Intervention in LLM Agent Trajectories via Streaming Structure-Aware Optimal Transport. arxiv. https://arxiv.org/abs/2610.12375 (2026-10-08)
[5] LLM Agents can Autonomously Hack Websites. hf-search. https://huggingface.co/papers/2402.06664 (2024-02-06)
[6] REMORY: Learning Residual Memory for Context Compaction. hf-daily. https://huggingface.co/papers/2610.11287 (2026-10-08)
[7] Reward Hacking Benchmark: Measuring Exploits in LLM Agents with Tool Use. hf-search. https://huggingface.co/papers/2605.02964 (2026-05-03)
[8] Tool-R0: Self-Evolving LLM Agents for Tool-Learning from Zero Data. hf-search. https://huggingface.co/papers/2602.21320 (2026-02-24)
[9] From Failure to Mastery: Generating Hard Samples for Tool-use Agents. hf-search. https://huggingface.co/papers/2601.01498 (2026-01-04)
[10] From Language to Action: A Review of Large Language Models as Autonomous Agents and Tool Users. hf-search. https://huggingface.co/papers/2508.17281 (2025-10-28)
