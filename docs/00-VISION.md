SYSTEM DESIGN TASK: Build a Local-First AI-Native Second Brain with Hybrid Retrieval

You are acting as a principal systems architect and senior engineer designing and implementing a real production-quality system.

Your task is to design and implement a local-first AI-native second brain that integrates:

- Obsidian markdown vault (source of truth)
- hybrid retrieval system
- graph knowledge layer
- RAG pipeline
- Claude Code as the primary interface

This system should be designed for long-term extensibility and real-world use, not as a toy prototype.

IMPORTANT PRINCIPLE

Claude Code must NOT perform the heavy reasoning over raw markdown files.

Instead:

Claude = orchestration layer  
Search system = retrieval + reasoning substrate

Claude should call retrieval services that return structured context.

Do NOT build a system where Claude just reads the vault directly.

--------------------------------

PRIMARY USER EXPERIENCE

The user interacts ONLY through Claude Code for:

- capturing ideas
- adding tasks
- saving links
- creating notes
- querying the vault
- retrieving insights
- running reviews
- exploring connections

Examples:

Capture this thought: ...  
Add a task for tomorrow: ...  
Save this GitHub repo: ...  
What do I know about agent memory?  
Show connections between GraphRAG and my retrieval architecture notes.  
Generate my weekly review.

Claude should translate these into commands that interact with the underlying system.

--------------------------------

SYSTEM REQUIREMENTS

1. STORAGE LAYER

The canonical knowledge base must be an Obsidian markdown vault.

The vault should support:

inbox  
daily notes  
planning notes  
source notes  
concept notes  
permanent notes  
project notes  
review notes  
AI-maintained metadata  

You must define:

- folder structure
- naming conventions
- note templates
- frontmatter schema

--------------------------------

2. CAPTURE WORKFLOWS

Claude commands should support capturing:

thoughts  
todos  
links (GitHub, Reddit, Twitter/X, articles)  
research notes  
project notes  
ideas  

Claude should convert captures into structured markdown using templates.

--------------------------------

3. HYBRID RETRIEVAL SYSTEM

The retrieval layer must include ALL of the following:

LEXICAL RETRIEVAL
(reverse index)

Used for:

titles  
repo names  
URLs  
code terms  
rare words  
exact phrase matching  

SEMANTIC RETRIEVAL
(embeddings)

Used for:

concept similarity  
idea recall  
topic discovery  

GRAPH RETRIEVAL

Used for:

note relationships  
source lineage  
project connections  
multi-hop reasoning  
concept exploration  

RERANKING

Used to refine final results before context assembly.

--------------------------------

4. QUERY PIPELINE

When a query arrives:

Step 1: classify query type  
Step 2: retrieve candidates from lexical index  
Step 3: retrieve candidates from vector index  
Step 4: retrieve graph neighbors  
Step 5: fuse results  
Step 6: rerank results  
Step 7: assemble final context  
Step 8: return structured context to Claude

Claude then synthesizes the answer.

--------------------------------

5. GRAPH KNOWLEDGE LAYER

Graph nodes should include:

Note  
Source  
Concept  
Project  
Topic  
Person  
Task  
TimePeriod  

Edges should include:

LINKS_TO  
DERIVED_FROM  
RELATED_TO  
BELONGS_TO_PROJECT  
ABOUT_TOPIC  
MENTIONS  
CAPTURED_ON  

Graph must be derived from vault metadata and links.

--------------------------------

6. RAG DESIGN

Do NOT implement naive chunking.

Implement:

note-level indexing  
chunk-level indexing for long notes  
metadata filtering  
graph-aware expansion  
deduplication  
reranked context assembly  

Focus on retrieval quality.

--------------------------------

7. PROCESSING WORKFLOWS

Support automated workflows:

inbox processing  
source summarization  
note promotion  
weekly review generation  
monthly review generation  
concept clustering  

--------------------------------

8. COMMAND INTERFACE

Claude should expose commands such as:

capture thought  
add task  
save link  
create source note  
create concept note  
process inbox  
generate review  
search notes  
explore connections  

--------------------------------

ARCHITECTURE EXPECTATIONS

The system should include:

vault storage layer  
markdown parser  
metadata extractor  
lexical indexer  
embedding indexer  
graph builder  
query router  
reranker  
context assembler  
Claude interface layer  

--------------------------------

IMPLEMENTATION STRATEGY

You must work in the following stages.

Stage 1 — Architecture

Define:

system architecture  
component diagram  
data flow  
technology choices  

Do NOT start coding yet.

--------------------------------

Stage 2 — Data Model

Define:

vault structure  
metadata schema  
note templates  
graph model  

--------------------------------

Stage 3 — Retrieval Design

Define:

lexical indexing system  
vector indexing system  
graph representation  
ranking fusion strategy  
reranking strategy  

--------------------------------

Stage 4 — Query Engine

Design:

query classification  
retrieval orchestration  
result fusion  
context construction  

--------------------------------

Stage 5 — Claude Interface

Design commands that Claude Code will use to interact with the system.

--------------------------------

Stage 6 — Implementation Plan

Provide a phased implementation roadmap.

--------------------------------

Stage 7 — Codebase Design

Provide a directory structure for the codebase.

--------------------------------

Stage 8 — Implementation

Generate code scaffolding and core components.

--------------------------------

QUALITY REQUIREMENTS

The system must:

prioritize retrieval quality  
remain local-first  
avoid vendor lock-in  
be extensible  
be debuggable  

Results must explain:

why a result matched  
which retrieval system found it  
how ranking occurred  

--------------------------------

DELIVERABLE FORMAT

Produce output in this order:

1. Executive summary  
2. Architecture design  
3. Technology stack choices  
4. Vault structure  
5. Metadata schema  
6. Note templates  
7. Retrieval architecture  
8. Graph model  
9. Query router design  
10. Processing workflows  
11. Claude command interface  
12. Implementation roadmap  
13. Codebase layout  
14. Code scaffold  
15. Setup instructions  
16. Example workflows  

--------------------------------

FINAL INSTRUCTION

The final system must allow:

knowledge capture through Claude Code  
knowledge retrieval through Claude Code  

But the search and retrieval system must do the heavy lifting, not Claude itself.

Claude should behave like an intelligent operator over a powerful retrieval engine.
