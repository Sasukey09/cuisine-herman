allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

// Force every plugin module up to compileSdk 36.
//
// Pinning compileSdk in app/build.gradle.kts only covers OUR module. The plugin
// subprojects (file_picker, flutter_secure_storage…) each carry their own, and
// pub resolves a flutter_plugin_android_lifecycle whose AAR metadata demands 36
// — while file_picker still compiles against 34. The release build then dies in
// `checkReleaseAarMetadata`.
//
// Reflection is used on purpose: the Android Gradle Plugin types are not on the
// root build script's classpath, so `BaseExtension` cannot be referenced here.
// compileSdk only widens the APIs available at compile time — minSdk and
// targetSdk are untouched, so no device is dropped and no runtime behaviour
// changes.
subprojects {
    afterEvaluate {
        val android = extensions.findByName("android") ?: return@afterEvaluate
        runCatching {
            android.javaClass
                .getMethod("compileSdkVersion", Int::class.javaPrimitiveType)
                .invoke(android, 36)
        }
    }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
