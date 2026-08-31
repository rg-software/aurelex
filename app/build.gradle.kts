import java.util.Properties
import java.io.FileInputStream

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Signing comes from env vars so CI can sign without committing the keystore:
//   AURELEX_KEYSTORE_PATH, AURELEX_KEYSTORE_PASSWORD,
//   AURELEX_KEY_ALIAS, AURELEX_KEY_PASSWORD
val hasSigningConfig = !System.getenv("AURELEX_KEYSTORE_PATH").isNullOrBlank()

val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) FileInputStream(f).use(::load)
}
val qtBase = localProps.getProperty("aurelex.qt.base") ?: ""
val qtHost = localProps.getProperty("aurelex.qt.host") ?: ""
val vcpkgRoot = localProps.getProperty("aurelex.vcpkg.root") ?: ""

// The engine submodule is pinned at a release tag; its VERSION is the index
// format version (design D5, task 6.3): an engine bump changes this string and
// therefore reindexes all indexes on the next scan.
val engineVersion = file("engine/VERSION").takeIf { it.exists() }?.readText()?.trim() ?: "unknown"

android {
    namespace = "aurelex.android"
    compileSdk = 36
    buildToolsVersion = "36.0.0"
    ndkVersion = "23.2.8568313"

    defaultConfig {
        applicationId = "aurelex.android"
        minSdk = 28
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
        externalNativeBuild {
            cmake {
                // See src/main/cpp/engine/CMakeLists.txt for the carve.
                // Machine-local Qt/vcpkg paths come from local.properties.
                arguments += listOf(
                    // Qt 6 android libs have NEEDED libc++_shared.so, so the
                    // app must use the shared STL (AGP then bundles it).
                    "-DANDROID_STL=c++_shared",
                    "-DQT_BASE=${qtBase}",
                    "-DQT_HOST_PATH=${qtHost}",
                    "-DVCPKG_BASE=${vcpkgRoot}"
                )
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/engine/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    signingConfigs {
        if (hasSigningConfig) {
            create("release") {
                storeFile = file(System.getenv("AURELEX_KEYSTORE_PATH"))
                storePassword = System.getenv("AURELEX_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("AURELEX_KEY_ALIAS")
                keyPassword = System.getenv("AURELEX_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Signed only when CI secrets provide a keystore (task 7.2);
            // local release builds remain unsigned so debug remains usable.
            if (hasSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    defaultConfig {
        // Injected on every build from the pinned engine submodule (D5/6.3).
        buildConfigField("String", "ENGINE_VERSION", "\"$engineVersion\"")
    }

    packaging {
        jniLibs {
            // Qt's libs contain a META-INF; avoid merge conflicts
            pickFirsts += listOf("META-INF/LICENSE.txt", "META-INF/NOTICE.txt", "META-INF/**")
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.10.00")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.core:core-ktx:1.15.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
}