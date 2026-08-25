#include <algorithm>
#include <chrono>
#include <cmath>
#include <functional>
#include <memory>
#include <string>

#include <cv_bridge/cv_bridge.h>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/image_encodings.hpp>
#include <sensor_msgs/msg/image.hpp>

class D0CameraPreview final : public rclcpp::Node
{
public:
  D0CameraPreview()
  : Node("d0_camera_preview")
  {
    this->declare_parameter<std::string>("color_topic", "/camera/camera/color/image_raw");
    this->declare_parameter<std::string>("depth_topic", "/camera/camera/depth/image_rect_raw");
    this->declare_parameter<std::string>("window", "D0 Camera Preview");
    color_topic_ = this->get_parameter("color_topic").as_string();
    depth_topic_ = this->get_parameter("depth_topic").as_string();
    window_ = this->get_parameter("window").as_string();

    color_sub_ = this->create_subscription<sensor_msgs::msg::Image>(
      color_topic_, rclcpp::SensorDataQoS(),
      std::bind(&D0CameraPreview::color_callback, this, std::placeholders::_1));
    if (!depth_topic_.empty()) {
      depth_sub_ = this->create_subscription<sensor_msgs::msg::Image>(
        depth_topic_, rclcpp::SensorDataQoS(),
        std::bind(&D0CameraPreview::depth_callback, this, std::placeholders::_1));
    }
    timer_ = this->create_wall_timer(
      std::chrono::milliseconds(33), std::bind(&D0CameraPreview::render, this));
    RCLCPP_INFO(get_logger(), "Previewing color=%s depth=%s", color_topic_.c_str(), depth_topic_.c_str());
  }

  ~D0CameraPreview() override
  {
    cv::destroyAllWindows();
  }

private:
  void color_callback(const sensor_msgs::msg::Image::ConstSharedPtr &message)
  {
    try {
      color_ = cv_bridge::toCvCopy(message, sensor_msgs::image_encodings::BGR8)->image;
    } catch (const cv_bridge::Exception &error) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "Color conversion failed: %s", error.what());
    }
  }

  void depth_callback(const sensor_msgs::msg::Image::ConstSharedPtr &message)
  {
    try {
      auto depth = cv_bridge::toCvCopy(message, sensor_msgs::image_encodings::TYPE_16UC1)->image;
      double min_value = 0.0;
      double max_value = 0.0;
      cv::minMaxLoc(depth, &min_value, &max_value, nullptr, nullptr);
      if (max_value <= min_value) {
        depth_ = cv::Mat::zeros(depth.size(), CV_8UC3);
        return;
      }
      cv::Mat normalized;
      depth.convertTo(normalized, CV_8UC1, 255.0 / (max_value - min_value),
                      -min_value * 255.0 / (max_value - min_value));
      cv::applyColorMap(normalized, depth_, cv::COLORMAP_TURBO);
    } catch (const cv_bridge::Exception &error) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "Depth conversion failed: %s", error.what());
    }
  }

  void render()
  {
    if (color_.empty() && depth_.empty()) {
      return;
    }
    cv::Mat frame;
    if (color_.empty()) {
      frame = depth_;
    } else if (depth_.empty()) {
      frame = color_;
    } else {
      const int height = std::min(color_.rows, depth_.rows);
      cv::Mat color_resized;
      cv::Mat depth_resized;
      cv::resize(color_, color_resized, cv::Size(0, 0),
                 static_cast<double>(height) / color_.rows,
                 static_cast<double>(height) / color_.rows);
      cv::resize(depth_, depth_resized, cv::Size(0, 0),
                 static_cast<double>(height) / depth_.rows,
                 static_cast<double>(height) / depth_.rows);
      cv::hconcat(color_resized, depth_resized, frame);
    }
    cv::imshow(window_, frame);
    const int key = cv::waitKey(1) & 0xff;
    if (key == 'q' || key == 27) {
      rclcpp::shutdown();
    }
  }

  std::string color_topic_;
  std::string depth_topic_;
  std::string window_;
  cv::Mat color_;
  cv::Mat depth_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr color_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr depth_sub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<D0CameraPreview>());
  rclcpp::shutdown();
  return 0;
}
