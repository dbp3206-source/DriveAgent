# Source Notes

Thư mục này ghi lại cách các tài nguyên đầu vào ảnh hưởng đến implementation. Tài liệu và ảnh gốc vẫn nằm ở vị trí người dùng cung cấp, không được sao chép vào Git để tránh phình repository hoặc vi phạm quyền phân phối.

- Tool Harness: registry sáu bước, least privilege, retry có chọn lọc, audit có che secret.
- Orchestration Harness: planning, task graph, state, routing, parallel execution và recovery.
- LangGraph: state, node, direct/conditional edge, checkpoint và vòng ReAct.
- RAG: chunk theo loại tài liệu, dense + lexical retrieval, filter theo user/file, RRF, citation.
- Memory: raw conversation, short-term summary, typed long-term memories, dedup và user isolation.

Nguồn LangGraph/Gemini được người dùng chỉ định:
`https://github.com/philschmid/gemini-samples/blob/main/guides/langgraph-react-agent.ipynb`.
Project mượn cấu trúc State + Nodes + conditional Edges + function calling, nhưng tự thêm
planner, checkpoint SQLite, giới hạn vòng lặp và Tool Registry có governance.
