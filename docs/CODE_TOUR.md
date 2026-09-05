# Hướng dẫn đọc code

Nếu bạn mới học, hãy đọc theo thứ tự:

1. `backend/app/db/models.py`: dữ liệu nào được lưu và cách tách user.
2. `backend/app/tools/registry.py`: sáu cổng kiểm soát một tool call.
3. `backend/app/tools/drive.py`: list, search và read Drive.
4. `backend/app/services/rag.py`: ingestion và hybrid retrieval.
5. `backend/app/services/memory.py`: typed memory và dedup.
6. `backend/app/agent/state.py`: state đi qua graph.
7. `backend/app/agent/orchestrator.py`: node, edge, tool wrapper và checkpoint.
8. `backend/app/api/`: REST API mỏng, giao nghiệp vụ cho service/registry.
9. `frontend/src/App.tsx` và `components/AppShell.tsx`: vỏ ứng dụng.
10. `frontend/src/pages/`: từng use case của người dùng.

Comment trong code giải thích lý do bảo mật hoặc kiến trúc. Các dòng hiển nhiên như gán biến không được comment để tránh nhiễu.
