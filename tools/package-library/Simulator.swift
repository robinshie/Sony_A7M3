import AppKit
import SwiftUI
import UniformTypeIdentifiers

enum SimulationMode: String, CaseIterable, Identifiable {
    case menu = "原厂菜单模型"
    case fl = "FL 创意外观模型"
    var id: Self { self }

    var guestPath: String {
        switch self {
        case .menu: "ui/build/a7m3-ui.elf"
        case .fl: "ui/build/fl-demo/a7m3-ui.elf"
        }
    }
}

enum SimulationGuest {
    static func read(_ url: URL) throws -> Data {
        let maxBytes = 24 * 1024 * 1024
        let fd = open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard fd >= 0 else { throw CocoaError(.fileReadNoSuchFile) }
        let input = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        defer { try? input.close() }
        var info = stat()
        guard fstat(fd, &info) == 0, info.st_mode & S_IFMT == S_IFREG,
              info.st_size >= 52, info.st_size <= maxBytes,
              let data = try input.read(upToCount: Int(info.st_size) + 1),
              data.count == info.st_size,
              Array(data.prefix(7)) == [0x7f, 0x45, 0x4c, 0x46, 1, 1, 1],
              Array(data[16..<20]) == [2, 0, 40, 0] else {
            throw CocoaError(.fileReadCorruptFile)
        }
        return data
    }
}

@MainActor
final class SimulatorModel: ObservableObject {
    @Published var mode = SimulationMode.fl
    @Published var isPicking = false
    @Published private(set) var isRunning = false
    @Published private(set) var status = ""
    @Published private var overrides: [SimulationMode: URL] = [:]
    private var process: Process?
    private var stopping = false

    var qemu: URL? {
        ["/opt/homebrew/bin/qemu-system-arm", "/usr/local/bin/qemu-system-arm"]
            .first(where: FileManager.default.isExecutableFile(atPath:))
            .map { URL(fileURLWithPath: $0) }
    }

    var guest: URL? {
        if let manual = overrides[mode] { return manual }
        let bundleParent = Bundle.main.bundleURL.deletingLastPathComponent()
        let lab = bundleParent.deletingLastPathComponent()
        guard bundleParent.lastPathComponent == "package-library", lab.lastPathComponent == ".lab" else { return nil }
        let path = lab.deletingLastPathComponent().appendingPathComponent(mode.guestPath)
        return FileManager.default.fileExists(atPath: path.path) ? path : nil
    }

    func choose(_ url: URL) {
        overrides[mode] = url
        status = ""
    }

    func start() {
        guard process == nil, let qemu, let guest else { return }
        let scoped = guest.startAccessingSecurityScopedResource()
        defer { if scoped { guest.stopAccessingSecurityScopedResource() } }
        let image: Data
        do {
            image = try SimulationGuest.read(guest)
        } catch {
            status = "无法读取 ARM 模型。请选择 ui/build 下由本项目生成的 a7m3-ui.elf。"
            return
        }

        let fm = FileManager.default
        let workspace = fm.temporaryDirectory.appendingPathComponent("a7m3-sim-\(UUID().uuidString)", isDirectory: true)
        var created = false
        do {
            try fm.createDirectory(at: workspace, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
            created = true
            let localGuest = workspace.appendingPathComponent("a7m3-ui.elf")
            try image.write(to: localGuest, options: .withoutOverwriting)
            let log = workspace.appendingPathComponent("qemu.log")
            try Data().write(to: log, options: .withoutOverwriting)
            let output = try FileHandle(forWritingTo: log)
            defer { try? output.close() }

            let job = Process()
            job.executableURL = qemu
            job.currentDirectoryURL = workspace
            job.arguments = [
                "-name", "A7M3 - \(mode.rawValue)", "-M", "realview-pbx-a9", "-smp", "1", "-m", "256",
                "-no-user-config", "-nodefaults", "-audio", "none", "-nic", "none", "-monitor", "none",
                "-display", "cocoa,zoom-to-fit=on", "-serial", "null",
                "-device", "loader,file=\(localGuest.path.replacingOccurrences(of: ",", with: ",,")),cpu-num=0"
            ]
            job.standardOutput = output
            job.standardError = output
            job.terminationHandler = { [weak self] finished in
                let code = finished.terminationStatus
                let detail = Self.readError(log)
                try? FileManager.default.removeItem(at: workspace)
                Task { @MainActor in self?.finished(code, detail: detail) }
            }
            try job.run()
            process = job
            isRunning = true
            stopping = false
            status = "QEMU 已启动。请切换到模拟窗口，按 M 打开菜单。"
        } catch {
            if created { try? fm.removeItem(at: workspace) }
            status = "无法启动 QEMU：\(error.localizedDescription)"
        }
    }

    func stop() {
        guard let process, process.isRunning, !stopping else { return }
        stopping = true
        status = "正在关闭 QEMU…"
        process.terminate()
    }

    private func finished(_ code: Int32, detail: String) {
        let normal = stopping || code == 0
        process = nil
        isRunning = false
        stopping = false
        status = normal ? "模拟窗口已关闭。" : "QEMU 退出（\(code)）。\(detail)"
    }

    nonisolated private static func readError(_ url: URL) -> String {
        guard let log = try? FileHandle(forReadingFrom: url) else { return "" }
        defer { try? log.close() }
        guard let data = try? log.read(upToCount: 1024) else { return "" }
        return String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

struct SimulatorView: View {
    @StateObject private var model = SimulatorModel()

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("QEMU · 菜单与 FL 仿真").font(.system(size: 26, weight: .semibold))
                Text("独立 ARM 模型 · 640 × 480 · 不运行发布 ZIP 或 Sony 原厂系统")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            GroupBox {
                VStack(alignment: .leading, spacing: 10) {
                    Picker("模型", selection: $model.mode) {
                        ForEach(SimulationMode.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .disabled(model.isRunning)
                    LabeledContent("QEMU", value: model.qemu?.path ?? "未找到 Homebrew 的 qemu-system-arm")
                    LabeledContent("模型 ELF", value: model.guest?.path ?? "未找到 \(model.mode.guestPath)")
                        .lineLimit(2)
                        .truncationMode(.middle)
                    HStack {
                        Button("选择本地 ELF…") { model.isPicking = true }.disabled(model.isRunning)
                        Spacer()
                        if model.isRunning {
                            Button("关闭模拟") { model.stop() }
                        } else {
                            Button("启动 QEMU") { model.start() }
                                .buttonStyle(.borderedProminent)
                                .disabled(model.guest == nil || model.qemu == nil)
                        }
                    }
                    if !model.status.isEmpty {
                        Text(model.status).font(.callout).fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(.vertical, 5)
            } label: {
                Label("本机仿真", systemImage: "display")
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("键盘：M 菜单，F 功能，方向键移动，Enter 确认，Esc 返回。")
                Text("FL 路径：在「创意风格」旁打开「创意外观」，也可从 Fn 进入。")
                Text("QEMU 用来验菜单和模拟色彩；UTM 只是过去实验的 USB 转接环境。")
                    .foregroundStyle(.secondary)
            }
            .font(.callout)
            Spacer(minLength: 0)
        }
        .padding(24)
        .frame(width: 680, alignment: .topLeading)
        .fileImporter(isPresented: $model.isPicking, allowedContentTypes: [.item]) { selection in
            if case .success(let url) = selection { model.choose(url) }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)) { _ in
            model.stop()
        }
    }
}
