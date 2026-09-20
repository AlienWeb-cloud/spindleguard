// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI

struct SetupWizard: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("First-run setup")
                .font(.title2.weight(.semibold))
            Text("Step \(state.wizardStep + 1) of \(AppState.wizardStepCount)")
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)
            ProgressView(
                value: Double(state.wizardStep + 1),
                total: Double(AppState.wizardStepCount)
            )
            stepBody
            Spacer(minLength: 0)
            if !state.error.isEmpty {
                Text(state.error)
                    .foregroundStyle(.red)
                    .textSelection(.enabled)
            }
            HStack {
                Button("Back") { state.wizardBack() }
                    .disabled(state.wizardStep == 0 || state.busy)
                Button("Skip wizard") { state.finishWizard(skipped: true) }
                    .disabled(state.busy)
                Spacer()
                if state.wizardStep < AppState.wizardStepCount - 1 {
                    Button("Continue") { state.wizardNext() }
                        .keyboardShortcut(.defaultAction)
                        .disabled(state.busy)
                } else {
                    Button("Finish") { state.finishWizard(skipped: false) }
                        .keyboardShortcut(.defaultAction)
                        .disabled(state.busy)
                }
            }
        }
        .padding(24)
        .frame(width: 560, height: 520)
    }

    @ViewBuilder
    private var stepBody: some View {
        switch state.wizardStep {
        case 0:
            VStack(alignment: .leading, spacing: 10) {
                Text("Welcome")
                    .font(.headline)
                Text("SpindleGuard is a test-only prototype. It does not protect evidence drives or confine agents.")
                Text("It refuses /Volumes and /dev. Active sessions stay on disk until you move them to the deletion bucket and purge.")
                Text("This wizard checks the Mac, optionally installs FUSE-T (only if you confirm), builds the broker and this app, verifies the install, then can create a disposable session.")
                    .foregroundStyle(.secondary)
                Text("Skip stores that you have seen this wizard so it does not open again. You can reopen it from Setup or the menu extra.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        case 1:
            VStack(alignment: .leading, spacing: 10) {
                Text("This Mac")
                    .font(.headline)
                Text("Doctor does not mount and does not open /dev.")
                    .foregroundStyle(.secondary)
                Button("Refresh checks") { state.refreshDoctor() }
                    .disabled(state.busy)
                CheckList(checks: state.checks)
            }
        case 2:
            VStack(alignment: .leading, spacing: 10) {
                Text("FUSE-T")
                    .font(.headline)
                Text("Needed only to mount. Homebrew is never run unless you confirm.")
                    .foregroundStyle(.secondary)
                Text(state.fuseInstall)
                    .font(.caption.monospaced())
                    .textSelection(.enabled)
                HStack {
                    Button("Copy install command") { state.copyFuseCommand() }
                    Button("Install FUSE-T…") { state.installFuse() }
                    Button("Open docs") { state.openFuseDocs() }
                }
                .disabled(state.busy)
                if state.fuseReady {
                    Text("FUSE-T runtime is present.")
                        .foregroundStyle(Color(red: 36 / 255, green: 88 / 255, blue: 201 / 255))
                }
            }
        case 3:
            VStack(alignment: .leading, spacing: 10) {
                Text("Build")
                    .font(.headline)
                Text("Run Setup builds the Swift app when swiftc is present, and the C broker only when FUSE-T is already installed.")
                    .foregroundStyle(.secondary)
                HStack {
                    Button("Preview setup") { state.previewSetup() }
                    Button("Run setup") { state.runSetup() }
                }
                .disabled(state.busy)
                if !state.setupJSON.isEmpty {
                    jsonBlock(state.setupJSON)
                }
            }
        case 4:
            VStack(alignment: .leading, spacing: 10) {
                Text("Verify")
                    .font(.headline)
                Text("Quick checks only: policy, scan, fixture bind, CLI. No FUSE mounts.")
                    .foregroundStyle(.secondary)
                Button("Verify install") { state.verifyInstall() }
                    .disabled(state.busy)
                if !state.verifyJSON.isEmpty {
                    jsonBlock(state.verifyJSON)
                }
            }
        default:
            VStack(alignment: .leading, spacing: 10) {
                Text("Disposable session")
                    .font(.headline)
                Text("Creates a retained source and mount under the session parent. Files stay until you bucket and purge them. After Finish you can Start from Broker when this Mac can mount.")
                    .foregroundStyle(.secondary)
                Button("New disposable session") { state.newSession() }
                    .disabled(state.busy)
                if !state.sessionRoot.isEmpty {
                    Text(state.sessionRoot)
                        .font(.caption.monospaced())
                        .textSelection(.enabled)
                }
            }
        }
    }
}
