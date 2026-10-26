import Foundation
#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#endif
#if canImport(FoundationModels)
import FoundationModels
#endif

struct Request: Decodable {
    let prompt: String
    let instructions: String?
}

struct Failure: Error, CustomStringConvertible {
    let description: String
    init(_ message: String) { description = message }
}

@main
struct AppleSystemModel {
    static func emit(_ object: [String: Any]) throws {
        let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
    }

    static func main() async {
        do {
            let args = Array(CommandLine.arguments.dropFirst())
            guard args.isEmpty || args == ["--availability"] else {
                throw Failure("Usage: apple-system-model [--availability]; sinon requête JSON sur stdin")
            }
            #if canImport(FoundationModels)
            if #available(macOS 26.0, *) {
                let model = SystemLanguageModel.default
                let identity: [String: Any] = [
                    "backend": "FoundationModels.SystemLanguageModel.default",
                    "weight_identity": "OS-managed; RC 24B115 weight identity not established",
                    "os": ProcessInfo.processInfo.operatingSystemVersionString,
                    "availability": String(describing: model.availability)
                ]
                guard case .available = model.availability else {
                    try emit(identity.merging(["status": "blocked", "inference_performed": false]) { _, rhs in rhs })
                    exit(2)
                }
                if args == ["--availability"] {
                    try emit(identity.merging(["status": "available", "inference_performed": false]) { _, rhs in rhs })
                    return
                }
                let data = FileHandle.standardInput.readDataToEndOfFile()
                guard data.count <= 1_048_576 else { throw Failure("La requête JSON dépasse 1 MiB") }
                guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                      Set(object.keys).isSubset(of: ["prompt", "instructions"]) else {
                    throw Failure("Objet JSON attendu, clés permises: prompt, instructions")
                }
                let request = try JSONDecoder().decode(Request.self, from: data)
                guard !request.prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                    throw Failure("prompt doit être une chaîne non vide")
                }
                let session: LanguageModelSession
                if let instructions = request.instructions {
                    session = LanguageModelSession(model: model, instructions: instructions)
                } else {
                    session = LanguageModelSession(model: model)
                }
                let response = try await session.respond(to: request.prompt)
                try emit(identity.merging([
                    "status": "success", "inference_performed": true,
                    "output": ["text": response.content]
                ]) { _, rhs in rhs })
                return
            }
            #endif
            throw Failure("FoundationModels nécessite un SDK Apple compatible et macOS 26+ éligible à Apple Intelligence")
        } catch {
            try? emit(["status": "error", "inference_performed": false,
                       "error": String(describing: error)])
            exit(2)
        }
    }
}
