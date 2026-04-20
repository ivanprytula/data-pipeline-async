# Daily AI Agent Commands

Prompt fragments and slash-command patterns for daily Copilot use. Paste or adapt these in the chat.
Organized by scope.

---

## Global Commands (any project)

### Session Start

```sh
/init
Audit my workspace, check for stale config in .copilot/ and .github/,
summarize what I was last working on from memory, and list the top 3 things
I should do today based on the project state.
```

### Code Review

```sh
Review [file or selection] and check for:
- OWASP Top 10 vulnerabilities
- N+1 queries or connection leaks
- Blocking calls in async code
- Hardcoded secrets or credentials
```

### Auto-Improve (invoke autoresearch skill)

```sh
Invoke autoresearch.
Goal: improve [metric] in [file/component].
Constraint: don't change the public API or break existing tests.
Run until you've made 3 measurable improvements or hit diminishing returns.
```

### Add Educational Comments

```sh
Invoke add-educational-comments on [file].
Target audience: mid-level engineer learning distributed systems.
Focus on the "why" not the "what".
```

### Commit Prep

```sh
Review my staged changes (or files I've edited today).
Suggest a conventional commit message (feat/fix/chore/docs/refactor).
Flag any security issues or missing tests before I commit.
```

### Cross-Project Skill Sync

```sh
I've improved [skill or instruction] in this project.
Walk me through what changed, confirm it's production-ready,
then run migrate-to-global.sh to push it to ~/.copilot/.
```

---

## APL-Specific Commands

### New Scenario Bootstrap

```sh
Invoke architecture-blueprint-generator.
New scenario: Scenario [N] — [Pattern Name].
Pattern to teach: [e.g. read replicas, circuit breaker, message queue].
Domain: e-commerce [orders/users/inventory].
Generate: README.md phases, docker-compose.yml skeleton, load_test.js stages,
and Prometheus metrics to watch.
```

### Scenario Audit

```sh
Audit scenario_[N]_[name]:
1. Does it follow the scenario checklist in .copilot/README.md?
2. Is docker-compose.yml using the container_name convention?
3. Does the README have all phases, the interview cheat sheet, and cleanup instructions?
4. Are there any hardcoded config values that should be in config.py?
```

### Breaking Point Analysis

```sh
I ran ./test.sh 200 30s and got [paste k6 output or error].
Diagnose what's causing the failure, pinpoint the bottleneck,
and explain it in terms a mid-level engineer could use in an interview answer.
```

### Pattern Comparison

```sh
I've implemented [pattern] in scenario_[N].
Compare it to the canonical implementation of this pattern.
What trade-offs did I make? What should I document in the README?
```

### DB Review (invoke postgresql-code-review skill)

```sh
Invoke postgresql-code-review on [models.py / init.sql / migration file].
Focus on: N+1 risks, missing indexes, connection pool interaction, and
whether the schema would survive the load tests in this scenario.
```

### Load Test Script Review

```sh
Review scripts/load_test.js in scenario_[N].
Does it properly exercise the breaking point?
Are the stages (ramp-up, sustained, teardown) correct?
Are thresholds set to catch the bottleneck we're teaching?
```

---

## End-of-Day Wrap-Up

```sh
Summarize what we accomplished today:
1. What files changed and why
2. Any architectural decisions made
3. What's still in progress
4. Suggested commit message(s)
Then update /memories/repo/data-pipeline-async.md with key decisions.
```

---

## Useful One-Liners (Paste Directly)

| Goal                                 | Command                                                                                                                                              |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Explain a concept for interview prep | `Explain [connection pool exhaustion] as if I'm answering an interview question. Include: what causes it, how to detect it, and two ways to fix it.` |
| Generate Grafana panel config        | `Generate a Grafana panel JSON for a time-series chart showing [active DB connections] from Prometheus metric [pg_stat_activity_count].`             |
| Write a migration                    | `Write an Alembic migration to [add index on orders.user_id]. Follow the conventions in .github/instructions/sql.instructions.md.`                   |
| Quick Docker debug                   | `I ran docker ps and see [paste output]. Identify any scenario containers that shouldn't be running and the cleanup command.`                        |
| Scenario README section              | `Write the "Interview Cheat Sheet" section for scenario_[N]. The pattern is [X], the bottleneck metric is [Y], the fix is [Z].`                      |
