import Foundation
import Vision
import ImageIO

// Only bibliographic metadata leaves this process. Body text is not serialized.
struct Line: Codable {
    let text: String
    let confidence: Float
    let x: Double
    let y: Double
    let height: Double
}

while let input = readLine() {
    autoreleasepool {
        do {
            let job = try JSONSerialization.jsonObject(with: Data(input.utf8)) as! [String: Any]
            let path = job["path"] as! String
            let year = job["year"] as! Int
            guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
                  let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
                throw NSError(domain: "image_decode", code: 1)
            }
            func recognize(top: Double, bottom: Double, scale: Int = 2) throws -> [Line] {
                let rect = CGRect(x: 0, y: Double(img.height) * top,
                                  width: Double(img.width), height: Double(img.height) * (bottom - top))
                guard let crop = img.cropping(to: rect),
                      let context = CGContext(data: nil, width: crop.width * scale, height: crop.height * scale,
                          bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                          bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return [] }
                context.interpolationQuality = .high
                context.draw(crop, in: CGRect(x: 0, y: 0, width: crop.width * scale, height: crop.height * scale))
                guard let resized = context.makeImage() else { return [] }
                let request = VNRecognizeTextRequest()
                request.recognitionLevel = .accurate
                request.recognitionLanguages = ["zh-Hans", "en-US"]
                request.usesLanguageCorrection = false
                try VNImageRequestHandler(cgImage: resized).perform([request])
                return (request.results ?? []).compactMap { obs -> Line? in
                guard let c = obs.topCandidates(1).first else { return nil }
                return Line(text: c.string, confidence: c.confidence,
                            x: obs.boundingBox.minX, y: top + (1 - obs.boundingBox.midY) * (bottom - top),
                            height: obs.boundingBox.height * (bottom - top))
                }
            }
            let lower: Double
            let upper: Double
            switch year {
            case 2015...2019: lower = 0.925; upper = 0.985
            case 2020: lower = 0.915; upper = 0.985
            case 2021: lower = 0.875; upper = 0.945
            case 2022: lower = 0.805; upper = 0.930
            case 2023: lower = 0.890; upper = 0.970
            case 2024: lower = 0.765; upper = 0.850
            default: lower = 0.880; upper = 0.925
            }
            let titleBand: (Double, Double)
            switch year {
            case 2015...2018: titleBand = (0.48, 0.64)
            case 2019...2021: titleBand = (0.53, 0.66)
            case 2022: titleBand = (0.415, 0.505)
            case 2023: titleBand = (0.585, 0.690)
            case 2024: titleBand = (0.390, 0.450)
            default: titleBand = (0.535, 0.635)
            }
            let allLines = year <= 2020 ? try recognize(top: 0, bottom: 1, scale: 1) : []
            let titleLines = year <= 2020 ? allLines.filter { $0.y > titleBand.0 && $0.y < titleBand.1 } : try recognize(top: titleBand.0, bottom: titleBand.1)
            let titles = titleLines.filter {
                let s = $0.text.replacingOccurrences(of: " ", with: "")
                return s.count <= 18 && (s.hasPrefix("宜") || s.hasPrefix("忌"))
            }
            let footerLines = year <= 2020 ? allLines : try recognize(top: lower - 0.015, bottom: upper)
            let attribution = footerLines.filter {
                $0.y >= lower && $0.y <= upper && !(year == 2021 && $0.x < 0.28)
            }
            let sourceLines = year == 2022 ? try recognize(top: 0.51, bottom: 0.795) : attribution
            var sources = sourceLines.filter {
                $0.y > (year == 2022 ? 0.52 : lower - 0.025) && $0.y < upper &&
                ($0.text.contains("《") || $0.text.contains("〈"))
            }.compactMap { line -> Line? in
                // Source titles only; never return surrounding body text here.
                let pattern = "[《〈][^》〉]{1,100}[》〉]"
                guard let range = line.text.range(of: pattern, options: .regularExpression) else { return nil }
                return Line(text: String(line.text[range]), confidence: line.confidence, x: line.x, y: line.y, height: line.height)
            }
            if year == 2022 && sources.isEmpty {
                // English song/book titles use the small source font without
                // Chinese book-title brackets. Body-size text is excluded.
                let candidates = sourceLines.filter {
                    $0.y > 0.60 && $0.y < 0.79 && $0.height < 0.024 &&
                    $0.text.count > 3 && $0.text.count <= 90 &&
                    $0.text.range(of: "[A-Za-z]", options: .regularExpression) != nil &&
                    $0.text.range(of: "[㐀-鿿。！？!?]", options: .regularExpression) == nil
                }
                if let line = candidates.last {
                    let title = line.text.replacingOccurrences(of: "\\s+[BMⓂⒷ]$", with: "", options: .regularExpression)
                    sources.append(Line(text: "《" + title + "》", confidence: line.confidence,
                                        x: line.x, y: line.y, height: line.height))
                }
            }
            let result = ["titles": titles, "attribution": attribution, "sources": sources]
            let data = try JSONEncoder().encode(result)
            print(String(decoding: data, as: UTF8.self))
            fflush(stdout)
        } catch {
            let data = try! JSONSerialization.data(withJSONObject: ["error": String(describing: error)])
            print(String(decoding: data, as: UTF8.self))
            fflush(stdout)
        }
    }
}
