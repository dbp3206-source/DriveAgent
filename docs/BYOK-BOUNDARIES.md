# BYOK credential boundaries

Each hosted invitee must save their own Gemini credential. A missing key does not
grant access to the process owner's environment key. Chat rejects that state with
`model_not_configured`; Google read tools can still operate with the user's own OAuth.
Local development retains its explicitly configured environment key as a single-owner
compatibility path. Do not expose that development profile as a multi-user service.

## Shared services, isolated model calls

SQL and vector-store ownership filters are necessary but insufficient: a shared
embedding client can still charge the wrong project or send data using the owner's
credential. API tool contexts now resolve the requesting user's saved key policy.
RAG and Memory use `scoped_embeddings` for index/query/save; direct Memory edits use
the same helper. A different credential/model receives a request-scoped client which
is closed even when provider work fails. The process-global settings/client is never
rotated for a different user.

The existing per-user Chat runtime pool remains separate. Quota-aware failover is
restricted to that user's explicitly opted-in credentials; it cannot borrow another
user's key. Google writes retain their own preview/approval/readback requirements.

## RAG provenance and compatibility

Local PDF chunks persist their original page markers, just like Drive PDF chunks.
Retrieval returns the page number from that durable chunk, not an inferred page.
Index fingerprints distinguish Gemini embeddings from local hashing vectors. Hashing
is a lexical fallback, not semantic equivalence to Gemini. Changing one usable key
for another does not itself invalidate Gemini vectors made with the same model.

The current pipeline version is `rag-page-aware-v5-local-provenance`. Old indexes
are retained but not served as current evidence. Reindex affected sources before
certifying their retrieval. This avoids deleting user data while refusing stale
provenance. Memory's historical embedding-profile migration still needs separate
verification; no claim of full semantic compatibility across old providers is made.

## Evidence and limits

Automated tests cover a real SQL/vector local-PDF index/search with page citation,
client cleanup on provider failure, hosted keyless rejection, settings immutability
and four concurrent API contexts with distinct fake credentials. These are deterministic
backend checks, not a public deployment or a live four-Google-account benchmark.
No private model call is needed for these tests. Full cloud persistence, browser OAuth,
BYOK and concurrency must still be checked on the eventual HTTPS staging URL.
