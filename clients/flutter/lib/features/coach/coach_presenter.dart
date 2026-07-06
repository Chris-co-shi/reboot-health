import '../../core/api_client.dart';

String coachFailureMessage(Object error) {
  if (error is ApiException && error.statusCode >= 400 && error.statusCode < 500) {
    return error.message;
  }
  return 'AI教练暂时不可用，请稍后重试';
}
