import 'api_client.dart';

class IdempotentAction {
  IdempotentAction(this._createKey);

  final String Function() _createKey;
  String? _key;

  String get key => _key ??= _createKey();

  void clear() {
    _key = null;
  }

  bool shouldRetainKey(Object error) {
    if (error is ApiException) {
      return error.statusCode == 408 || error.statusCode == 429 || error.statusCode >= 500;
    }
    return true;
  }

  Future<T> run<T>(Future<T> Function(String idempotencyKey) action) async {
    try {
      final T result = await action(key);
      clear();
      return result;
    } catch (error) {
      if (!shouldRetainKey(error)) {
        clear();
      }
      rethrow;
    }
  }
}
