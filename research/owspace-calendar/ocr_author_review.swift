import Foundation
import Vision
import ImageIO

struct CreditLine: Codable {let text:String;let confidence:Float;let x:Double;let y:Double;let height:Double}
struct CreditResult: Codable {let top:Double;let bottom:Double;let multilingual:[CreditLine];let latin:[CreditLine]}
while let input=readLine() {
    autoreleasepool {
        do {
            let job=try JSONSerialization.jsonObject(with:Data(input.utf8)) as! [String:Any]
            let path=job["path"] as! String,year=job["year"] as! Int
            guard let src=CGImageSourceCreateWithURL(URL(fileURLWithPath:path) as CFURL,nil),let img=CGImageSourceCreateImageAtIndex(src,0,nil) else {throw NSError(domain:"decode",code:1)}
            func recognize(_ top:Double,_ bottom:Double,_ languages:[String]) throws -> [CreditLine] {
                guard let crop=img.cropping(to:CGRect(x:0,y:Double(img.height)*top,width:Double(img.width),height:Double(img.height)*(bottom-top))),
                      let context=CGContext(data:nil,width:crop.width*3,height:crop.height*3,bitsPerComponent:8,bytesPerRow:0,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.noneSkipLast.rawValue) else {return []}
                context.interpolationQuality = .high
                context.draw(crop,in:CGRect(x:0,y:0,width:crop.width*3,height:crop.height*3))
                let req=VNRecognizeTextRequest();req.recognitionLevel = .accurate
                req.recognitionLanguages=languages;req.usesLanguageCorrection=false
                try VNImageRequestHandler(cgImage:context.makeImage()!).perform([req])
                return (req.results ?? []).compactMap {obs in
                    guard let c=obs.topCandidates(1).first else{return nil}
                    return CreditLine(text:c.string,confidence:c.confidence,x:obs.boundingBox.minX,y:top+(1-obs.boundingBox.midY)*(bottom-top),height:obs.boundingBox.height*(bottom-top))
                }
            }
            let langs=["zh-Hans","ko-KR","ja-JP","ru-RU","en-US","fr-FR","de-DE"]
            var top:Double,bottom:Double
            switch year {
            case 2015...2019:top=0.922;bottom=0.991
            case 2020:top=0.910;bottom=0.990
            case 2021:top=0.875;bottom=0.946
            case 2022:top=0.800;bottom=0.935
            case 2023:top=0.903;bottom=0.970
            case 2024:top=0.765;bottom=0.845
            default:top=0.880;bottom=0.925
            }
            var middle:[CreditLine]?=nil
            if year==2022 {
                let portrait=try recognize(0.73,0.815,langs).filter{$0.height>0.025 && $0.text.range(of:"^(作家|小说家|诗人|歌手|导演|演员|音乐家|艺术家|哲学家|剧作家|词作者|乐队|记者|画家|科学家|人类学家)",options:.regularExpression) != nil}
                if !portrait.isEmpty {top=0.73;bottom=0.815;middle=portrait}
            }
            if year==2023 && (job["layout_variant"] as? String)=="reader_question" {
                let lines=try recognize(0.17,0.56,langs)
                if let credit=lines.first(where:{$0.text.range(of:"(作家|小说家|诗人|编剧|导演|演员|记者|歌手|摄影家|哲学家)",options:.regularExpression) != nil}) {
                    top=max(0.17,credit.y-0.065);bottom=min(0.56,credit.y+0.055)
                    middle=lines.filter{$0.y>top && $0.y<bottom && $0.x>0.35}
                } else {top=0.17;bottom=0.17;middle=[]}
            }
            let multi=try middle ?? recognize(top,bottom,langs)
            let latin=bottom>top ? try recognize(top,bottom,["en-US","fr-FR","de-DE","it-IT","es-ES","pt-BR"]) : []
            let result=CreditResult(top:top,bottom:bottom,multilingual:multi,latin:latin)
            print(String(decoding:try JSONEncoder().encode(result),as:UTF8.self));fflush(stdout)
        } catch {print("{\"error\":\"author_region_ocr_failed\"}");fflush(stdout)}
    }
}
