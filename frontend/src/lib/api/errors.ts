/**
 * Ошибки API, соответствующие контракту бэкенда `{error: {code, message, details}}`.
 */

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;
  readonly requestId?: string;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
    this.requestId = payload.request_id;
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let payload: ApiErrorPayload;
    try {
      const body = (await response.json()) as { error?: ApiErrorPayload };
      payload = body.error ?? {
        code: 'http_error',
        message: `HTTP ${response.status}`,
      };
    } catch {
      payload = { code: 'http_error', message: `HTTP ${response.status}` };
    }
    return new ApiError(response.status, payload);
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}
