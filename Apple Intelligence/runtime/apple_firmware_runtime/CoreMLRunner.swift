// Public Core ML backend. Built on macOS by the Python CLI, never emulated on Linux.
import Foundation
import CoreML
import CoreFoundation
import CoreVideo
import CoreImage
import ImageIO
import Dispatch

struct Failure: Error {
    let code: String
    let message: String
}

func fail(_ message: String, _ code: String = "invalid_inputs") throws -> Never {
    throw Failure(code: code, message: message)
}

func finiteNumber(_ raw: Any, _ context: String) throws -> NSNumber {
    guard let number = raw as? NSNumber,
          CFGetTypeID(number) != CFBooleanGetTypeID(), number.doubleValue.isFinite else {
        try fail("\(context) must be a finite number; booleans are rejected")
    }
    return number
}

func int64Number(_ raw: Any, _ context: String) throws -> NSNumber {
    // String form preserves all Int64 values through JSON consumers with a 53-bit mantissa.
    if let string = raw as? String, let value = Int64(string) { return NSNumber(value: value) }
    let number = try finiteNumber(raw, context)
    let value = number.doubleValue
    guard value.rounded(.towardZero) == value,
          value >= -9223372036854775808.0, value < 9223372036854775808.0 else {
        try fail("\(context) must be an int64 (decimal string is accepted)")
    }
    return NSNumber(value: number.int64Value)
}

func featureSchema(_ description: MLFeatureDescription) -> [String: Any] {
    var result: [String: Any] = ["name": description.name, "type": String(describing: description.type),
                               "type_raw_value": description.type.rawValue, "optional": description.isOptional]
    if let c = description.multiArrayConstraint {
        result["multiarray"] = ["shape": c.shape, "data_type": String(describing: c.dataType),
                                "data_type_raw_value": c.dataType.rawValue,
                                "shape_constraint_type": String(describing: c.shapeConstraint.type),
                                "enumerated_shapes": c.shapeConstraint.enumeratedShapes,
                                "dimension_ranges": c.shapeConstraint.sizeRangeForDimension.map { value -> [String: Any] in
                                    let range = value.rangeValue
                                    return ["minimum": range.location, "length": range.length]
                                }]
    }
    if let c = description.imageConstraint {
        result["image"] = ["width": c.pixelsWide, "height": c.pixelsHigh, "pixel_format": c.pixelFormatType,
                           "input_encoding": "{image_path: absolute file path}; exact size required, no implicit resize"]
    }
    if let c = description.dictionaryConstraint {
        result["dictionary"] = ["key_type": String(describing: c.keyType)]
    }
    if let c = description.sequenceConstraint {
        result["sequence"] = ["element_type": String(describing: c.valueDescription.type),
                              "minimum_count": c.countRange.location, "count_range_length": c.countRange.length]
    }
    return result
}

func multiArray(_ raw: Any, _ constraint: MLMultiArrayConstraint, _ name: String) throws -> MLMultiArray {
    guard let object = raw as? [String: Any], Set(object.keys).isSubset(of: ["shape", "data"]),
          let dimensions = object["shape"] as? [Any],
          let flat = object["data"] as? [Any] else {
        try fail("\(name): multiarray input requires {shape: [positive integers], data: [flat numbers]}")
    }
    var shape: [NSNumber] = []
    var count = 1
    for dimension in dimensions {
        let value = try int64Number(dimension, "\(name).shape")
        guard value.int64Value > 0, value.int64Value <= Int64(Int.max),
              count <= 100_000_000 / value.intValue else { try fail("\(name): array too large or invalid shape") }
        shape.append(value)
        count *= value.intValue
    }
    guard count == flat.count else { try fail("\(name): data count \(flat.count) differs from shape element count \(count)") }
    // Allocate the model's declared type; no guessed dtype or implicit quantization.
    let array = try MLMultiArray(shape: shape, dataType: constraint.dataType)
    for (index, rawValue) in flat.enumerated() {
        if constraint.dataType == .int32 {
            let value = try int64Number(rawValue, name)
            guard value.int64Value >= Int64(Int32.min), value.int64Value <= Int64(Int32.max) else {
                try fail("\(name): integer exceeds int32")
            }
            array[index] = value
        } else {
            let value = try finiteNumber(rawValue, name)
            array[index] = value
            guard array[index].doubleValue.isFinite else { try fail("\(name): number overflows declared array type") }
        }
    }
    return array
}

func makeValue(_ raw: Any, description: MLFeatureDescription) throws -> MLFeatureValue {
    let name = description.name
    let result: MLFeatureValue
    switch description.type {
    case .int64:
        result = MLFeatureValue(int64: try int64Number(raw, name).int64Value)
    case .double:
        result = MLFeatureValue(double: try finiteNumber(raw, name).doubleValue)
    case .string:
        guard let string = raw as? String else { try fail("\(name) must be a string") }
        result = MLFeatureValue(string: string)
    case .multiArray:
        guard let constraint = description.multiArrayConstraint else { try fail("Missing array constraint", "unsupported_feature") }
        result = MLFeatureValue(multiArray: try multiArray(raw, constraint, name))
    case .dictionary:
        guard let entries = raw as? [String: Any], let constraint = description.dictionaryConstraint else {
            try fail("\(name) must be a JSON dictionary")
        }
        var values: [AnyHashable: NSNumber] = [:]
        for (key, value) in entries {
            if constraint.keyType == .int64 {
                guard let keyNumber = Int64(key) else { try fail("\(name): dictionary key must be int64") }
                values[NSNumber(value: keyNumber)] = try finiteNumber(value, name)
            } else if constraint.keyType == .string {
                values[key] = try finiteNumber(value, name)
            } else { try fail("\(name): unsupported dictionary key type", "unsupported_feature") }
        }
        result = try MLFeatureValue(dictionary: values)
    case .sequence:
        guard let elements = raw as? [Any], let constraint = description.sequenceConstraint else {
            try fail("\(name) must be a sequence array")
        }
        if constraint.valueDescription.type == .string {
            guard let strings = elements as? [String] else { try fail("\(name) must contain only strings") }
            result = MLFeatureValue(sequence: MLSequence(strings: strings))
        } else if constraint.valueDescription.type == .int64 {
            result = MLFeatureValue(sequence: MLSequence(int64s: try elements.map { try int64Number($0, name) }))
        } else { try fail("\(name): unsupported sequence type", "unsupported_feature") }
    case .image:
        guard let object = raw as? [String: Any], Set(object.keys) == ["image_path"],
              let path = object["image_path"] as? String, path.hasPrefix("/"),
              let constraint = description.imageConstraint else {
            try fail("\(name): image requires {image_path: absolute local path}")
        }
        let url = URL(fileURLWithPath: path)
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { try fail("\(name): cannot decode image") }
        // Do not silently invent preprocessing. A caller supplies the exact dimensions.
        guard image.width == constraint.pixelsWide, image.height == constraint.pixelsHigh else {
            try fail("\(name): image dimensions \(image.width)x\(image.height) differ from model's default \(constraint.pixelsWide)x\(constraint.pixelsHigh)")
        }
        result = try MLFeatureValue(cgImage: image, constraint: constraint, options: nil)
    default:
        try fail("\(name): feature type \(description.type) is not supported by this JSON transport", "unsupported_feature")
    }
    guard description.isAllowedValue(result) else { try fail("\(name): value violates modelDescription constraints") }
    return result
}

final class Inputs: MLFeatureProvider {
    let values: [String: MLFeatureValue]
    init(_ values: [String: MLFeatureValue]) { self.values = values }
    var featureNames: Set<String> { Set(values.keys) }
    func featureValue(for featureName: String) -> MLFeatureValue? { values[featureName] }
}

func encodeOutput(_ value: MLFeatureValue) throws -> Any {
    if value.isUndefined { return NSNull() }
    switch value.type {
    case .int64: return ["type": "int64", "decimal": String(value.int64Value)]
    case .double:
        guard value.doubleValue.isFinite else { try fail("Non-finite output", "output_encoding_failed") }
        return value.doubleValue
    case .string: return value.stringValue
    case .multiArray:
        guard let array = value.multiArrayValue else { try fail("Missing array output", "output_encoding_failed") }
        let data = (0..<array.count).map { array[$0] }
        guard data.allSatisfy({ $0.doubleValue.isFinite }) else { try fail("Non-finite output array", "output_encoding_failed") }
        return ["shape": array.shape, "data_type": String(describing: array.dataType), "data": data]
    case .dictionary:
        var object: [String: NSNumber] = [:]
        for (key, number) in value.dictionaryValue {
            guard number.doubleValue.isFinite else { try fail("Non-finite dictionary output", "output_encoding_failed") }
            object[String(describing: key)] = number
        }
        return object
    case .sequence:
        guard let sequence = value.sequenceValue else { try fail("Missing sequence output", "output_encoding_failed") }
        if sequence.type == .string { return sequence.stringValues }
        return ["type": "int64_sequence", "decimal": sequence.int64Values.map { String($0.int64Value) }]
    case .image:
        guard let buffer = value.imageBufferValue else { try fail("Missing image output", "output_encoding_failed") }
        let image = CIImage(cvPixelBuffer: buffer)
        guard let cg = CIContext().createCGImage(image, from: image.extent) else { try fail("Cannot encode image", "output_encoding_failed") }
        guard let data = CFDataCreateMutable(nil, 0),
              let destination = CGImageDestinationCreateWithData(data, "public.png" as CFString, 1, nil) else {
            try fail("Cannot encode PNG", "output_encoding_failed")
        }
        CGImageDestinationAddImage(destination, cg, nil)
        guard CGImageDestinationFinalize(destination) else { try fail("PNG encoding failed", "output_encoding_failed") }
        return ["png_base64": (data as Data).base64EncodedString(), "width": cg.width, "height": cg.height]
    default:
        try fail("Unsupported output type: \(value.type)", "unsupported_feature")
    }
}

func perform(_ request: [String: Any]) throws -> [String: Any] {
    guard let action = request["action"] as? String, ["inspect", "predict"].contains(action),
          let path = request["model_path"] as? String else { try fail("Invalid backend request", "protocol_error") }
    let configuration = MLModelConfiguration()
    switch request["compute"] as? String ?? "cpu" {
    case "cpu": configuration.computeUnits = .cpuOnly
    case "all": configuration.computeUnits = .all
    case "cpu-and-gpu": configuration.computeUnits = .cpuAndGPU
    case "cpu-and-ne":
        if #available(macOS 13.0, *) { configuration.computeUnits = .cpuAndNeuralEngine }
        else { try fail("cpu-and-ne requires macOS 13 or later", "backend_unavailable") }
    default: try fail("Unknown compute unit", "protocol_error")
    }
    let original = URL(fileURLWithPath: path)
    var compiled: URL? = nil
    defer { if let url = compiled { try? FileManager.default.removeItem(at: url) } }
    let loadURL: URL
    if ["mlmodel", "mlpackage"].contains(original.pathExtension) {
        do { compiled = try MLModel.compileModel(at: original); loadURL = compiled! }
        catch { try fail("Core ML compilation rejected the firmware artifact: \(error)", "coreml_compile_failed") }
    } else { loadURL = original }
    let model: MLModel
    do { model = try MLModel(contentsOf: loadURL, configuration: configuration) }
    catch { try fail("Core ML cannot load this artifact on this host: \(error)", "coreml_load_failed") }
    let description = model.modelDescription
    let schema: [String: Any] = [
        "inputs": description.inputDescriptionsByName.keys.sorted().map { featureSchema(description.inputDescriptionsByName[$0]!) },
        "outputs": description.outputDescriptionsByName.keys.sorted().map { featureSchema(description.outputDescriptionsByName[$0]!) },
        "source": "MLModel.modelDescription from the actually loaded model",
        "semantics": "Feature names and constraints only; no inferred preprocessing or labels"
    ]
    var response: [String: Any] = ["schema": schema, "prediction_performed": false,
                                   "compute_requested": request["compute"] ?? "cpu",
                                   "host": ProcessInfo.processInfo.operatingSystemVersionString]
    if action == "inspect" { return response }
    guard let rawInputs = request["inputs"] as? [String: Any] else { try fail("inputs must be an object") }
    let expected = Set(description.inputDescriptionsByName.keys)
    let extra = Set(rawInputs.keys).subtracting(expected)
    guard extra.isEmpty else { try fail("Unknown input features: \(extra.sorted())") }
    var values: [String: MLFeatureValue] = [:]
    for (name, feature) in description.inputDescriptionsByName {
        if let raw = rawInputs[name], !(raw is NSNull) { values[name] = try makeValue(raw, description: feature) }
        else if !feature.isOptional { try fail("Missing required input feature: \(name)") }
    }
    let start = DispatchTime.now().uptimeNanoseconds
    let prediction: MLFeatureProvider
    do { prediction = try model.prediction(from: Inputs(values)) }
    catch { try fail("Core ML prediction failed: \(error)", "coreml_prediction_failed") }
    let elapsed = DispatchTime.now().uptimeNanoseconds - start
    var outputs: [String: Any] = [:]
    for name in prediction.featureNames.sorted() {
        guard let value = prediction.featureValue(for: name) else { try fail("Missing predicted feature \(name)", "output_encoding_failed") }
        outputs[name] = try encodeOutput(value)
    }
    response["outputs"] = outputs
    response["prediction_performed"] = true
    response["prediction_seconds"] = Double(elapsed) / 1_000_000_000
    return response
}

do {
    let input = FileHandle.standardInput.readDataToEndOfFile()
    guard let object = try JSONSerialization.jsonObject(with: input) as? [String: Any] else { try fail("Request must be object", "protocol_error") }
    let response = try perform(object)
    let encoded = try JSONSerialization.data(withJSONObject: response, options: [.sortedKeys])
    FileHandle.standardOutput.write(encoded)
    FileHandle.standardOutput.write(Data([10]))
} catch {
    let failure = error as? Failure
    let response = ["error": failure?.code ?? "coreml_failed", "message": failure?.message ?? String(describing: error)]
    let encoded = try! JSONSerialization.data(withJSONObject: response, options: [.sortedKeys])
    FileHandle.standardOutput.write(encoded)
    FileHandle.standardOutput.write(Data([10]))
    exit(2)
}
