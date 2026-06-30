import { useLocation } from 'react-router-dom'

/** Read query params from the current URL. */
export function useQuery(): URLSearchParams {
  return new URLSearchParams(useLocation().search)
}
