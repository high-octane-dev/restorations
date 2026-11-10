#![feature(path_file_prefix)]
use binrw::*;
use clap::{arg, command, Parser};
use dds::{D3DFormat, Dds, NewD3dParams};
use x_flipper_360::*;

use std::{
    convert::TryInto,
    io::{Read, Seek, Write},
    path::{Path, PathBuf},
};

#[derive(BinRead, Debug)]
pub struct NativeHeader {
    pub native: TextureHeader,
    pub flags: u32,
}

impl NativeHeader {
    pub fn streamable(&self) -> bool {
        (self.flags & 1) != 0
    }
    pub fn delay_loaded(&self) -> bool {
        (self.flags & 2) != 0
    }
    pub fn srgb(&self) -> bool {
        (self.flags & 4) != 0
    }
    pub fn cpu_memory(&self) -> bool {
        (self.flags & 8) != 0
    }
}

#[derive(Debug, BinRead)]
pub struct ThbEntry {
    pub native_header_offset: u32,
    pub body_offset: u32,
    pub texture_len: u32,
}

#[derive(Debug, BinRead)]
pub struct ThbFile {
    entry_count: u32,
    #[br(count = entry_count)]
    pub entries: Vec<ThbEntry>,
    #[br(count = entry_count)]
    pub native_headers: Vec<NativeHeader>,
}

fn interpolate(c0: (u8, u8, u8, u8), c1: (u8, u8, u8, u8), factor: f32) -> (u8, u8, u8, u8) {
    let lerp = |a, b| (a as f32 + (b as f32 - a as f32) * factor).trunc() as u8;
    (
        lerp(c0.0, c1.0),
        lerp(c0.1, c1.1),
        lerp(c0.2, c1.2),
        lerp(c0.3, c1.3),
    )
}

pub fn decode_ctx1_to_r8g8b8a8(ctx1_data: &[u8], width: u32, height: u32) -> Vec<u8> {
    let mut output = vec![0u8; width as usize * height as usize * 4];
    let blocks_w = width / 4;
    let blocks_h = height / 4;
    let mut idx = 0;

    for by in 0..blocks_h {
        for bx in 0..blocks_w {
            let c0_r = ctx1_data[idx];
            let c0_g = ctx1_data[idx + 1];
            let c1_r = ctx1_data[idx + 2];
            let c1_g = ctx1_data[idx + 3];
            let indices = u32::from_le_bytes(ctx1_data[idx + 4..idx + 8].try_into().unwrap());
            idx += 8;

            let color0 = (c0_r, c0_g, 255, 255);
            let color1 = (c1_r, c1_g, 255, 255);

            let (color2, color3) = if (c0_r, c0_g) > (c1_r, c1_g) {
                (
                    interpolate(color0, color1, 1.0 / 3.0),
                    interpolate(color0, color1, 2.0 / 3.0),
                )
            } else {
                (interpolate(color0, color1, 0.5), (0, 0, 0, 0))
            };

            let palette = [color0, color1, color2, color3];

            for py in 0..4 {
                for px in 0..4 {
                    let pixel_index = ((indices >> (2 * (py * 4 + px))) & 0b11) as usize;
                    let color = palette[pixel_index];
                    let x = bx * 4 + px;
                    let y = by * 4 + py;
                    let offset = (y * width + x) * 4;
                    output[offset as usize..offset as usize + 4]
                        .copy_from_slice(&[color.2, color.1, color.0, color.3]);
                }
            }
        }
    }

    output
}

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    #[arg(long = "thb")]
    texture_header_file: PathBuf,

    #[arg(long = "tbb")]
    texture_body_file: PathBuf,

    #[arg(long = "tstreams")]
    tstream_folder: PathBuf,

    #[arg(long = "out")]
    output_folder: PathBuf,
}

fn main() {
    let args = Args::parse();
    let package_name = args
        .texture_header_file
        .file_prefix()
        .unwrap()
        .to_str()
        .unwrap();

    let mut f = std::fs::File::open(&args.texture_header_file).unwrap();
    let thb = ThbFile::read_be(&mut f).unwrap();

    let mut tbb = std::fs::File::open(&args.texture_body_file).unwrap();

    for (i, entry) in thb.native_headers.iter().enumerate() {
        let stream_path = args
            .tstream_folder
            .join(format!("{}_{}.tstream", package_name, i));
        let is_tstream = std::fs::exists(&stream_path).unwrap();
        let meta = entry.native.metadata();
        let texture_size: [u8; 4] = meta.texture_size().to_le_bytes();
        let mip_count = if !entry.streamable() {
            1
        } else {
            1 // 1.max(meta.max_mip_level() - meta.min_mip_level() - 4) as u32
        };

        let mut body = vec![0u8; thb.entries[i].texture_len as usize];
        tbb.seek(std::io::SeekFrom::Start(thb.entries[i].body_offset as u64))
            .unwrap();
        tbb.read_exact(&mut body).unwrap();

        match &meta.dimension() {
            Dimension::TwoDOrStacked => {
                let size = TextureSize2D::from_bytes(texture_size);
                if is_tstream {
                    println!(
                        "TStream: {} Is of Size: {}x{}, Format: {:?}",
                        i,
                        size.width() as u32 + 1,
                        size.height() as u32 + 1,
                        meta.format()
                    );
                    let mut stream_data = std::fs::read(&stream_path).unwrap();
                    stream_data.extend_from_slice(&body);

                    let mut out = std::fs::File::create(
                        args.output_folder
                            .join(format!("{}_{}.dds", package_name, i)),
                    )
                    .unwrap();
                    let mapped = match meta.format() {
                        TextureFormat::Dxt1 => Format::Dxt1,
                        TextureFormat::Ctx1 => Format::Ctx1,
                        TextureFormat::Dxt3AAs1_1_1_1 => Format::Dxt3,
                        TextureFormat::Dxt3A => Format::Dxt3,
                        TextureFormat::Dxt4_5 => Format::Dxt5,
                        // TextureFormat::_1_5_5_5 => Format::A1R5G5B5,
                        _ => {
                            println!(
                                "TStream: {} Has unimlpemented format: {:?}! Skipping...",
                                i,
                                meta.format()
                            );
                            continue;
                        }
                    };
                    if meta.format() == TextureFormat::Ctx1 {
                        let config = Config {
                            width: size.width() as u32 + 1,
                            height: size.height() as u32 + 1,
                            depth: None,
                            pitch: meta.pitch() as u32,
                            tiled: meta.tiled(),
                            packed_mips: meta.packed_mips(),
                            format: Format::Ctx1,
                            mipmap_levels: Some(mip_count),
                            base_address: meta.base_address() as u32,
                            mip_address: meta.mip_address() as u32,
                        };

                        let mut unswizzled_ctx1 = Vec::new();
                        x_flipper_360::convert_to_linear(
                            &config,
                            &stream_data,
                            &mut unswizzled_ctx1,
                        );

                        let rgba = decode_ctx1_to_r8g8b8a8(
                            &unswizzled_ctx1,
                            size.width() as u32 + 1,
                            size.height() as u32 + 1,
                        );
                        let mut dds = Dds::new_d3d(NewD3dParams {
                            height: config.height,
                            width: config.width,
                            depth: config.depth,
                            format: D3DFormat::A8R8G8B8,
                            mipmap_levels: config.mipmap_levels,
                            caps2: None,
                        })
                        .unwrap();
                        // Octane Engine games on PC do this stupid thing where they store a non-standard SRGB flag in `caps3` inside the DDS headers.
                        dds.header.caps3 = entry.srgb() as u32;
                        dds.data.copy_from_slice(&rgba);
                        dds.write(&mut out).unwrap();
                    } else {
                        let config = Config {
                            width: size.width() as u32 + 1,
                            height: size.height() as u32 + 1,
                            depth: None,
                            pitch: meta.pitch() as u32,
                            tiled: meta.tiled(),
                            packed_mips: meta.packed_mips(),
                            format: mapped,
                            mipmap_levels: Some(mip_count),
                            base_address: meta.base_address() as u32,
                            mip_address: meta.mip_address() as u32,
                        };
                        x_flipper_360::convert_to_dds(
                            &config,
                            &stream_data,
                            &mut out,
                            entry.srgb(),
                        )
                        .unwrap();
                    }
                } else {
                    println!(
                        "TBuf: {} Is of Size: {}x{}, Format: {:?}",
                        i,
                        size.width() as u32 + 1,
                        size.height() as u32 + 1,
                        meta.format()
                    );
                    let mut out = std::fs::File::create(
                        args.output_folder
                            .join(format!("{}_{}.dds", package_name, i)),
                    )
                    .unwrap();
                    let mapped = match meta.format() {
                        TextureFormat::Dxt1 => Format::Dxt1,
                        TextureFormat::Ctx1 => Format::Ctx1,
                        TextureFormat::Dxt3AAs1_1_1_1 => Format::Dxt3,
                        TextureFormat::Dxt3A => Format::Dxt3,
                        TextureFormat::Dxt4_5 => Format::Dxt5,
                        // TextureFormat::_1_5_5_5 => Format::A1R5G5B5,
                        _ => {
                            println!(
                                "TBuf: {} Has unimlpemented format: {:?}! Skipping...",
                                i,
                                meta.format()
                            );
                            continue;
                        }
                    };
                    if meta.format() == TextureFormat::Ctx1 {
                        let config = Config {
                            width: size.width() as u32 + 1,
                            height: size.height() as u32 + 1,
                            depth: None,
                            pitch: meta.pitch() as u32,
                            tiled: meta.tiled(),
                            packed_mips: meta.packed_mips(),
                            format: Format::Ctx1,
                            mipmap_levels: Some(mip_count),
                            base_address: meta.base_address() as u32,
                            mip_address: meta.mip_address() as u32,
                        };

                        let mut unswizzled_ctx1 = Vec::new();
                        x_flipper_360::convert_to_linear(&config, &body, &mut unswizzled_ctx1);

                        let rgba = decode_ctx1_to_r8g8b8a8(
                            &unswizzled_ctx1,
                            size.width() as u32 + 1,
                            size.height() as u32 + 1,
                        );

                        let mut dds = Dds::new_d3d(NewD3dParams {
                            height: config.height,
                            width: config.width,
                            depth: config.depth,
                            format: D3DFormat::A8R8G8B8,
                            mipmap_levels: config.mipmap_levels,
                            caps2: None,
                        })
                        .unwrap();
                        // Octane Engine games on PC do this stupid thing where they store a non-standard SRGB flag in `caps3` inside the DDS headers.
                        dds.header.caps3 = entry.srgb() as u32;
                        dds.data.copy_from_slice(&rgba);
                        dds.write(&mut out).unwrap();
                    } else {
                        let config = Config {
                            width: size.width() as u32 + 1,
                            height: size.height() as u32 + 1,
                            depth: None,
                            pitch: meta.pitch() as u32,
                            tiled: meta.tiled(),
                            packed_mips: meta.packed_mips(),
                            format: mapped,
                            mipmap_levels: Some(mip_count),
                            base_address: meta.base_address() as u32,
                            mip_address: meta.mip_address() as u32,
                        };
                        x_flipper_360::convert_to_dds(&config, &body, &mut out, entry.srgb())
                            .unwrap();
                    }
                }
            }
            Dimension::CubeMap => {
                if is_tstream {
                    println!("TStream: {} Is a CubeMap! Skipping...", i);
                } else {
                    println!("TBuf: {} Is a CubeMap! Skipping...", i);
                }
                continue;
                /*
                let size = TextureSizeStack::from_bytes(texture_size);
                if is_tstream {
                    println!(
                        "TStream: {} Is of Size: {}x{}x{}, Format: {:?}",
                        i,
                        size.width() as u32 + 1,
                        size.height() as u32 + 1,
                        size.depth() as u32 + 1,
                        meta.format()
                    );
                    let stream_data = std::fs::read(&stream_name).unwrap();
                    let mut out = std::fs::File::create(args.output_folder.join(format!("{}_{}.dds", package_name, i))).unwrap();
                    let mapped = match meta.format() {
                        TextureFormat::Dxt1 => Format::Dxt1,
                        TextureFormat::Dxt3AAs1_1_1_1 => Format::Dxt3,
                        TextureFormat::Dxt3A => Format::Dxt3,
                        TextureFormat::Dxt4_5 => Format::Dxt5,
                        // TextureFormat::_1_5_5_5 => Format::A1R5G5B5,
                        _ => {
                            println!("TStream: {} Has unimlpemented format: {:?}! Skipping...", i, meta.format());
                            continue;
                        },
                    };
                    let config = Config {
                        width: size.width() as u32 + 1,
                        height: size.height() as u32 + 1,
                        depth: Some(size.depth() as u32 + 1),
                        pitch: meta.pitch() as u32,
                        tiled: meta.tiled(),
                        packed_mips: meta.packed_mips(),
                        format: mapped,
                        mipmap_levels: Some(
                            mip_count
                        ),
                        base_address: meta.base_address() as u32,
                        mip_address: meta.mip_address() as u32,
                    };
                    x_flipper_360::convert_to_dds_cubemap(&config, &stream_data, &mut out).unwrap();
                } else {
                    println!(
                        "TBuf: {} Is of Size: {}x{}x{}, Format: {:?}",
                        i,
                        size.width() as u32 + 1,
                        size.height() as u32 + 1,
                        size.depth() as u32 + 1,
                        meta.format()
                    );
                    let mut out = std::fs::File::create(args.output_folder.join(format!("{}_{}.dds", package_name, i))).unwrap();
                    let mapped = match meta.format() {
                        TextureFormat::Dxt1 => Format::Dxt1,
                        TextureFormat::Dxt3AAs1_1_1_1 => Format::Dxt3,
                        TextureFormat::Dxt3A => Format::Dxt3,
                        TextureFormat::Dxt4_5 => Format::Dxt5,
                        // TextureFormat::_1_5_5_5 => Format::A1R5G5B5,
                        _ => {
                            println!("TBuf: {} Has unimlpemented format: {:?}! Skipping...", i, meta.format());
                            continue;
                        },
                    };
                    let config = Config {
                        width: size.width() as u32 + 1,
                        height: size.height() as u32 + 1,
                        depth: Some(size.depth() as u32 + 1),
                        pitch: meta.pitch() as u32,
                        tiled: meta.tiled(),
                        packed_mips: meta.packed_mips(),
                        format: mapped,
                        mipmap_levels: Some(
                            mip_count
                        ),
                        base_address: meta.base_address() as u32,
                        mip_address: meta.mip_address() as u32,
                    };
                    x_flipper_360::convert_to_dds_cubemap(&config, &body, &mut out).unwrap();
                }
                */
            }
            /*
            Dimension::OneD => {
                println!("1D: {:#?}", TextureSize1D::from_bytes(texture_size));
            }
            Dimension::ThreeD => {
                println!("3D: {:#?}", TextureSize3D::from_bytes(texture_size));
            }
            */
            _ => {
                println!("Entry: {} Is {:?}", i, meta.dimension());
            }
        };
    }
}
