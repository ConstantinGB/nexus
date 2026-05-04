# Concept Paper: A Local, Tool-Using AI Agent Architecture for Low-VRAM Systems

## Abstract

This paper describes a modular architecture for a locally running AI agent designed to operate reliably on consumer hardware with approximately 6 GB of VRAM. The system separates intent detection, planning, tool execution, validation, and response generation into distinct components rather than relying on a single large model to perform all tasks. The goal is to maximize reliability, minimize compute cost, and make tool use predictable through strict structured outputs and validation layers.

## 1. Problem Statement

A local AI agent that performs real work must do more than chat. It must:

* interpret user intent,
* decide whether a tool is needed,
* produce valid structured arguments,
* execute tools safely,
* and return a coherent answer.

On limited hardware, a monolithic approach is fragile. A single model asked to do classification, reasoning, formatting, and tool selection will often be inconsistent, especially under tight resource constraints. The design goal here is not maximum general intelligence. The goal is dependable operation under limited compute.

## 2. System Goals

The proposed architecture is optimized for:

* **Local execution** without dependence on cloud inference for the core workflow.
* **Low resource usage** on a machine with 6 GB VRAM and a consumer CPU.
* **Reliable tool calling** with minimal ambiguity.
* **Modular specialization**, so that small models or deterministic components handle narrow tasks.
* **Debuggability**, so each step is inspectable and replaceable.
* **Scalability through composition**, not through a larger base model.

## 3. Core Design Principle

The central principle is:

> **Do not let one model decide everything.**

Instead, divide the agent into layers with strict contracts between them. Each layer has a narrow purpose and returns a validated output. This reduces failure modes and makes the system easier to maintain.

## 4. High-Level Architecture

The agent can be implemented as a pipeline with the following stages:

1. **Intent Router**

   * Classifies the user message.
   * Determines whether the input is a command, question, follow-up, or tool request.

2. **Planner**

   * Uses a medium-size local LLM.
   * Decides whether to respond directly or request a tool action.

3. **Argument Generator**

   * Produces structured tool arguments.
   * Must emit schema-compliant output only.

4. **Validator**

   * Checks format, schema, and required fields.
   * Rejects malformed or incomplete output.

5. **Tool Executor**

   * Runs local Python functions, shell commands, or API calls.
   * Has no reasoning ability of its own.

6. **Responder**

   * Converts tool results into user-facing text.
   * Optional, depending on whether tool outputs are already suitable.

This architecture is better thought of as a **workflow engine** than as a conversational bot.

## 5. Component Responsibilities

### 5.1 Intent Router

The intent router should be cheap and fast. Its purpose is not deep reasoning. It should answer questions such as:

* Is this a command or a question?
* Does this likely require a tool?
* Is this a formatting request?
* Is this a simple yes/no classification task?

Suitable implementations include:

* rule-based heuristics,
* fastText classifiers,
* small embedding-based classifiers,
* or very small transformer models.

This component should run on CPU.

### 5.2 Planner

The planner is the central LLM-backed component. It interprets intent and decides the next step. It should not execute tools directly. It should only produce a structured plan.

Typical planner outputs:

* “respond directly,”
* “call tool X with arguments Y,”
* “ask for clarification,”
* “delegate to a specialized formatter.”

The planner should be constrained to structured output, ideally JSON.

### 5.3 Argument Generator

This component converts a plan into exact tool parameters. It must be strict and deterministic in form. Its job is not to decide whether a tool is needed, only how the request maps to the tool schema.

For example, instead of generating prose, it should produce:

```json
{
  "tool": "calendar.update",
  "arguments": {
    "date": "2026-05-04",
    "title": "Project review",
    "time": "15:00"
  }
}
```

### 5.4 Validator

The validator is essential. It is the boundary between language model output and executable action. It should verify:

* valid JSON,
* required fields,
* allowed tool names,
* argument types,
* value ranges,
* and any domain-specific constraints.

If validation fails, the system should either retry with tighter instructions or route the issue back to the planner.

### 5.5 Tool Executor

The tool executor is a pure action layer. It should not interpret free text. It should accept only validated structured input and dispatch the corresponding local function or API call.

Examples:

* calendar modification,
* file manipulation,
* shell script execution,
* web search,
* image generation,
* speech transcription,
* text reformatting.

### 5.6 Responder

The responder turns tool output into a user-facing response. In some cases, tool output can be sent directly. In others, especially when results are technical or verbose, a small model can convert the output into clearer language.

This step is optional.

## 6. Recommended Model Roles

On low-memory systems, different tasks should be assigned to different model classes.

### 6.1 Small Classification Models

Use these for:

* intent detection,
* yes/no classification,
* message type detection,
* simple routing.

These can often run entirely on CPU with negligible cost.

### 6.2 Embedding Models

Use these for:

* semantic routing,
* similarity search,
* memory retrieval,
* prompt type matching.

Embedding models are usually much cheaper than generative models and are well suited for lookup and classification-like tasks.

### 6.3 Main Reasoning Model

Use a 7B-class quantized model for:

* planning,
* ambiguity resolution,
* multi-step reasoning,
* structured tool selection.

This model should not be responsible for everything. It should be asked to reason, not to parse, classify, validate, and execute at the same time.

### 6.4 Specialist Models

Use narrow models or deterministic tools for:

* speech recognition,
* image generation,
* markdown conversion,
* LaTeX formatting,
* basic extraction,
* shell command generation.

The best specialization is often not another LLM, but a non-LLM component.

## 7. Reliability Strategy

Reliability comes from constraining the system, not from trusting the model more.

### 7.1 Structured Output Only

The planner and argument generator should produce only a machine-readable schema. Free-form text should not be accepted at the tool boundary.

### 7.2 Validation Before Execution

No tool should run unless its input passes validation. This is the most important guardrail in the architecture.

### 7.3 Retry on Failure

If the model produces invalid output, the system should retry with a stricter prompt or narrower schema. Failure should be explicit, not silent.

### 7.4 Deterministic Fallbacks

Where possible, use deterministic alternatives:

* regex parsing,
* rule-based classification,
* schema templates,
* hardcoded tool wrappers.

LLMs should be used where ambiguity exists, not where structure is already known.

## 8. Execution Flow

A typical request passes through the system as follows:

1. The user sends a message.
2. The intent router classifies the message.
3. The planner decides whether a tool is needed.
4. If a tool is needed, the argument generator produces structured input.
5. The validator checks the structure.
6. The executor runs the tool.
7. The responder transforms the result into final output.

This flow can be implemented synchronously or asynchronously. The important point is that each stage has a clearly defined contract.

## 9. Concurrency Strategy

On a machine with limited VRAM, multiple LLMs should not all be loaded onto GPU at once. A more realistic strategy is:

* keep the main model resident,
* run lightweight classifiers on CPU,
* run embeddings on CPU,
* offload audio and other preprocessing tasks to CPU,
* serialize heavy generation tasks,
* and use asynchronous processing for non-LLM steps.

This gives the appearance of parallelism without exhausting memory.

## 10. Why This Works Better Than a Single Agent Prompt

A monolithic agent prompt asks one model to do too many things at once. That causes:

* inconsistent tool selection,
* malformed tool arguments,
* verbose or irrelevant responses,
* fragile behavior under prompt variation,
* and poor reproducibility.

A modular workflow avoids these problems by separating responsibilities. Each component solves one narrow problem well.

## 11. Implementation Style

A practical implementation should use:

* typed message objects,
* a tool registry,
* async-compatible components,
* schema validation,
* and explicit logging at every step.

A useful internal design is a finite-state workflow:

```text
INPUT
  → INTENT ROUTER
  → PLANNER
  → ARGUMENT GENERATOR
  → VALIDATOR
  → TOOL EXECUTOR
  → RESPONDER
```

This structure is simple, debuggable, and easy to extend.

## 12. Conclusion

A reliable local AI agent on low-VRAM hardware is best built as a modular system of narrow components rather than as one large autonomous model. The core idea is to reserve generative reasoning for the few places where it is actually needed, while using cheap classifiers, embeddings, validators, and deterministic executors everywhere else.

The result is a system that is:

* more stable,
* easier to inspect,
* cheaper to run,
* and far better suited to dependable tool use.

The central lesson is straightforward: **reliability comes from architecture, not just model size.**

If you want, I can turn this into a more formal RFC-style version with explicit interfaces, data contracts, and a sample message flow.
