import Foundation
import Vision
import ImageIO

// A separate QA pass returns only month/day candidates, never body text.
while let input=readLine() {
    autoreleasepool {
        do {
            let job=try JSONSerialization.jsonObject(with:Data(input.utf8)) as! [String:Any]
            let path=job["path"] as! String
            let year=job["year"] as! Int
            let req=VNRecognizeTextRequest()
            req.recognitionLevel = .accurate
            req.recognitionLanguages=["zh-Hans","en-US"]
            req.usesLanguageCorrection=false
            try VNImageRequestHandler(url:URL(fileURLWithPath:path)).perform([req])
            var months=[Int](),days=[Int]()
            let cn=["一月":1,"二月":2,"三月":3,"四月":4,"五月":5,"六月":6,"七月":7,"八月":8,"九月":9,"十月":10,"十一月":11,"十二月":12]
            let en=["JANUARY":1,"FEBRUARY":2,"MARCH":3,"APRIL":4,"MAY":5,"JUNE":6,"JULY":7,"AUGUST":8,"SEPTEMBER":9,"OCTOBER":10,"NOVEMBER":11,"DECEMBER":12]
            for obs in req.results ?? [] {
                guard let c=obs.topCandidates(1).first else {continue}
                let y=1-obs.boundingBox.midY
                let s=c.string.replacingOccurrences(of:" ",with:"")
                if year==2025 && y<0.13 && obs.boundingBox.minX<0.3,let n=cn[s] {months.append(n)}
                if year==2024 && y>0.15 && y<0.27 {
                    for (name,n) in en where s.uppercased().contains(name) {months.append(n)}
                }
                if y>0.15 && y<0.58 && obs.boundingBox.height>0.08 && s.range(of:"^[0-9]{1,2}$",options:.regularExpression) != nil,let n=Int(s),n>0,n<32 {days.append(n)}
            }
            let data=try JSONSerialization.data(withJSONObject:["months":Array(Set(months)).sorted(),"days":Array(Set(days)).sorted()])
            print(String(decoding:data,as:UTF8.self));fflush(stdout)
        } catch {
            print("{\"months\":[],\"days\":[]}");fflush(stdout)
        }
    }
}
