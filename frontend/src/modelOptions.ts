export interface ModelOption {
  id: string
  name: string
  speed: string
  availability: string
  description: string
}

/** Labels describe product behavior only; live quota belongs to provider diagnostics. */
export const AVAILABLE_MODELS: ModelOption[] = [
  {
    id: 'gemini-3.5-flash-lite',
    name: 'Gemini 3.5 Flash Lite',
    speed: 'Phản hồi nhanh',
    availability: 'Ưu tiên tiết kiệm hạn mức',
    description: 'Phù hợp câu hỏi thường ngày và thao tác tài liệu ngắn, tiết kiệm quota.',
  },
  {
    id: 'gemini-3.8-flash',
    name: 'Gemini 3.8 Flash',
    speed: 'Suy luận chuyên sâu',
    availability: 'Bản Preview nghiên cứu',
    description: 'Phù hợp tác vụ cần tổng hợp, đối chiếu số liệu và lập luận phức tạp đa chiều.',
  },
]
