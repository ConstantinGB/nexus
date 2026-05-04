# Concept Paper: Designing AI-Readable Input Formats for Local Agent Systems

## Abstract

Large language models (LLMs) do not “understand” textual input in the human sense. They infer patterns from training data and perform best when the input format is explicit, regular, and commonly represented in that data. For local AI systems, especially constrained hardware setups, the practical goal is not to make the model “smarter” through richer presentation alone, but to make the information easier to parse, validate, and act on. This paper argues that Markdown and JSON are highly effective because they are structured, predictable, and widely represented, while diagram-like formats are usually less effective unless they are converted into explicit machine-readable structures. For coding and agent workflows, the strongest improvement comes from constraint and schema, not from visual presentation.

---

## 1. Problem Statement

The central question is how to present information to an AI system so that it can interpret it reliably, quickly, and with minimal ambiguity. In local agentic systems, the choice of representation matters because models have limited context, limited compute, and varying reliability across tasks.

A common intuition is that richer representations, such as diagrams, should help the model “understand” better. In practice, that is only sometimes true. The model does not reason over visual structure unless it is explicitly multimodal and even then, text-based structure tends to be more reliable for operational tasks.

---

## 2. Core Assumption

An LLM does not interpret format semantically in the way a human does. It recognizes patterns.

Therefore:

* familiar formats are easier to parse,
* explicit structure reduces ambiguity,
* and machine-verifiable schemas outperform expressive but loose representations.

This means that the best format is usually not the most expressive one, but the one with the clearest constraints.

---

## 3. Relative Readability of Common Formats

### 3.1 JSON

JSON is one of the most AI-readable formats available.

**Strengths**

* strict syntax
* unambiguous structure
* easy to validate
* ideal for tool calls and data exchange

**Use cases**

* function arguments
* routing decisions
* task decomposition
* structured outputs

JSON is especially effective because the model can be instructed to produce it directly, and downstream code can verify whether the output is valid.

---

### 3.2 Markdown

Markdown is highly readable for both humans and models.

**Strengths**

* hierarchical structure
* common in training data
* good balance between free text and organization
* useful for instructions, notes, and concept descriptions

**Use cases**

* documentation
* prompt scaffolding
* task specifications
* readable summaries

Markdown is less strict than JSON, but still far more structured than raw prose.

---

### 3.3 Natural Language Prose

Natural language is the most flexible and the least reliable format.

**Strengths**

* expressive
* intuitive for humans
* useful for open-ended reasoning

**Weaknesses**

* ambiguous
* easy to misparse
* difficult to validate automatically

This is suitable for high-level reasoning but poor for exact machine execution.

---

### 3.4 Code

Code is usually parsed well when the syntax is common and the language is heavily represented in training data.

**Strengths**

* highly structured
* rich semantic signals
* useful for reasoning about functions, dependencies, and behavior

**Best practice**

* provide code directly rather than paraphrasing it
* include signatures, tests, and comments where relevant

Models generally do better with actual code than with prose descriptions of code.

---

## 4. Diagrams as Input to AI

Diagrams can be useful, but mainly as human-facing representations. For AI systems, diagrams are only helpful when they are encoded in a textual form that preserves the relationships explicitly.

### 4.1 Diagram Languages in Text Form

Examples include:

* Mermaid
* ASCII diagrams
* Graphviz-like notation

These can work when:

* the syntax is simple,
* the structure is shallow,
* and the model has seen enough examples of the format.

However, they are still just text. The model does not truly “see” the diagram as a human would.

### 4.2 Limitations

Diagram syntax becomes less reliable when:

* the graph is large,
* the relationships are nested,
* layout conveys meaning,
* or the notation is uncommon.

In those cases, the model may misread edges, nodes, or hierarchy.

### 4.3 Recommendation

If the goal is machine reliability, convert the diagram into an explicit graph structure rather than depending on visual syntax.

For example, instead of a flowchart, represent the system as:

```json
{
  "nodes": ["input", "classifier", "planner", "tool"],
  "edges": [
    ["input", "classifier"],
    ["classifier", "planner"],
    ["planner", "tool"]
  ]
}
```

This preserves the relationships while eliminating ambiguity.

---

## 5. What Actually Improves Model Performance

The biggest gains usually come from **constraint**, not presentation.

### 5.1 Explicit Schemas

A model performs better when it is told exactly what fields to produce and what each field means.

Example:

```json
{
  "task": "classify_input",
  "allowed_labels": ["command", "question", "answer", "follow_up"]
}
```

This reduces the model’s degrees of freedom and makes the result easier to validate.

### 5.2 Narrow Output Contracts

For tool calling, the best pattern is to require the model to output only a small structured object.

Example:

* action
* tool name
* arguments
* confidence

This is far more reliable than asking the model to reason and act in one unconstrained step.

### 5.3 Validation and Retries

Even a good model will occasionally fail to produce valid structured output. Reliability comes from:

* parsing,
* schema validation,
* rejection of malformed output,
* and retrying when necessary.

---

## 6. Application to Coding Systems

For code-focused AI systems, the most useful inputs are:

### High-value inputs

* actual source code
* function signatures
* tests
* API schemas
* docstrings with precise semantics

### Medium-value inputs

* Markdown explanations
* architectural summaries
* annotated examples

### Low-value inputs

* visual metaphors
* informal diagram layouts
* ambiguous prose descriptions of code structure

If the AI needs to understand code better, it is usually better to provide:

1. the code itself,
2. a structured summary,
3. and any constraints or expected outputs.

A diagram can supplement this, but should not replace the code or schema.

---

## 7. Recommended Representation Strategy

For a local AI agent system, the best representation strategy is layered:

### Human-facing layer

Use Markdown for:

* documentation
* task framing
* explanations
* design notes

### Machine-facing layer

Use JSON or typed schemas for:

* tool calls
* routing
* state transitions
* structured outputs

### Code layer

Use actual source code for:

* execution logic
* function behavior
* dependency structure

### Diagram layer

Use only when:

* architecture communication matters,
* or the diagram is converted into a structured graph representation.

---

## 8. Design Principle

The right question is not:

> “Which format looks more informative?”

The right question is:

> “Which format minimizes ambiguity while preserving the relationships the model needs?”

That usually means:

* JSON for control,
* Markdown for readable context,
* code for exact semantics,
* and diagrams only when they are translated into explicit structure.

---

## 9. Conclusion

AI systems do not benefit equally from all textual representations. Their performance depends less on visual richness and more on regularity, familiarity, and explicit constraints. Markdown and JSON work well because they are highly structured and common. Diagrams may help humans, but they only help models when their content is converted into a machine-readable graph or schema.

For practical agent design, especially on constrained local hardware, the most effective strategy is to reduce ambiguity, enforce output structure, and treat visual representation as secondary to explicit data representation.

---

## Recommended Default Stack

* **Markdown** for human-readable explanation
* **JSON** for tool and agent communication
* **Code** for actual logic
* **Structured graphs** instead of diagrams when machine parsing matters

---

## Final Principle

If a representation can be turned into a strict schema, it will usually be more useful to an AI than a visually expressive alternative.
