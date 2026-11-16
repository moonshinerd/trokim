import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Simula o contrato de cancelamento do transporte sem abrir sockets.
http.Client abortableClient(
  Future<http.Response> Function(http.Request) handler, {
  void Function()? onAbort,
}) => MockClient.streaming((request, bodyStream) async {
  final forwarded = http.Request(request.method, request.url)
    ..headers.addAll(request.headers)
    ..bodyBytes = await bodyStream.toBytes();
  final response = handler(forwarded);
  final abort = request is http.Abortable ? request.abortTrigger : null;
  final result = await Future.any([
    response,
    if (abort != null)
      abort.then<http.Response>((_) {
        onAbort?.call();
        throw http.RequestAbortedException(request.url);
      }),
  ]);
  return http.StreamedResponse(
    Stream.value(result.bodyBytes),
    result.statusCode,
    headers: result.headers,
  );
});
