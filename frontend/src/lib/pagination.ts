export interface PaginationMeta {
  page: number
  page_size: number
  total_count: number
  total_pages: number
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: PaginationMeta
}
